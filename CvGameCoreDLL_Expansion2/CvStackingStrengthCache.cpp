#include "CvGameCoreDLLPCH.h"
#include "CvStackingStrengthCache.h"
#include <algorithm>
#include <vector>
#include <cstring>
#include "LintFree.h"

namespace CvStackingStrengthCache
{
	bool Key::operator==(const Key& other) const
	{
		return std::memcmp(values, other.values, sizeof(values)) == 0;
	}
	namespace
	{
		struct Hash
		{
			size_t operator()(const Key& key) const
			{
				// Four independent full-word lanes shorten the serial dependency
				// chain. Every input bit is mixed; full-key equality is unchanged.
				unsigned int v1 = 0x9e3779b1u + 0x85ebca77u;
				unsigned int v2 = 0x85ebca77u, v3 = 0u, v4 = 0u - 0x9e3779b1u;
				const size_t words = sizeof(key.values) / sizeof(key.values[0]);
				size_t i = 0;
				for (; i + 4 <= words; i += 4)
				{
					v1 = (v1 + (unsigned int)key.values[i]) * 0x9e3779b1u;
					v1 = (v1 << 13) | (v1 >> 19);
					v2 = (v2 + (unsigned int)key.values[i+1]) * 0x85ebca77u;
					v2 = (v2 << 17) | (v2 >> 15);
					v3 = (v3 + (unsigned int)key.values[i+2]) * 0xc2b2ae3du;
					v3 = (v3 << 11) | (v3 >> 21);
					v4 = (v4 + (unsigned int)key.values[i+3]) * 0x27d4eb2fu;
					v4 = (v4 << 19) | (v4 >> 13);
				}
				unsigned int result = ((v1 << 1) | (v1 >> 31)) + ((v2 << 7) | (v2 >> 25))
					+ ((v3 << 12) | (v3 >> 20)) + ((v4 << 18) | (v4 >> 14));
				result += (unsigned int)sizeof(key.values);
				for (; i < words; ++i)
				{
					result += (unsigned int)key.values[i] * 0xc2b2ae3du;
					result = ((result << 17) | (result >> 15)) * 0x27d4eb2fu;
				}
				result ^= result >> 15;
				result *= 0x85ebca77u;
				result ^= result >> 13;
				result *= 0xc2b2ae3du;
				result ^= result >> 16;
				return (size_t)result;
			}
		};
		// Indices survive vector growth. The ring replaces only the oldest slot;
		// bucket links retain full-key equality and never depend on addresses.
		struct Node { Key key; int value, next, previous; size_t hash; };
		std::vector<Node> nodes;
		std::vector<int> buckets;
		unsigned int oldest = 0;
		size_t Find(const Key& key, size_t hash)
		{
			if (buckets.empty()) return (size_t)-1;
			for (int i = buckets[hash & (buckets.size() - 1)]; i != -1; i = nodes[i].next)
				if (nodes[i].hash == hash && nodes[i].key == key) return (size_t)i;
			return (size_t)-1;
		}
		void Link(unsigned int index)
		{
			Node& node = nodes[index];
			const size_t bucket = node.hash & (buckets.size() - 1);
			node.previous = -1;
			node.next = buckets[bucket];
			if (node.next != -1) nodes[node.next].previous = index;
			buckets[bucket] = index;
		}
		void Unlink(unsigned int index)
		{
			Node& node = nodes[index];
			if (node.previous != -1) nodes[node.previous].next = node.next;
			else buckets[node.hash & (buckets.size() - 1)] = node.next;
			if (node.next != -1) nodes[node.next].previous = node.previous;
		}
		__declspec(align(4)) volatile LONG owner = 0;
		__declspec(align(4)) volatile LONG epoch = 0;
		LONG cachedEpoch = 0;
		unsigned int depth = 0;
		Stats stats = {};
		CallbackCapabilityProvider capabilityProvider = NULL;
		bool capabilitiesReady=false, capabilitiesSupported=false, validationSupported=false, capabilitiesBuilding=false;
		unsigned int capabilities=0;
		// The live lock/option check costs an engine call per lookup. The search
		// releases the GameCore lock only at its yields, which bump the epoch, and
		// the event options are fixed for a game, so one check per epoch suffices.
		bool liveValidated=false;
		LONG liveValidatedEpoch=0;
		// Every loading/rebuild suspension is local to the invoking thread;
		// atomic epoch invalidation also cancels an owning foreign computation.
		static __declspec(thread) unsigned int previewSuspensionDepth=0;
		LONG Read(volatile LONG& value)
		{
#if defined(_MSC_VER) && _MSC_VER == 1500 && defined(_M_IX86) && \
	!defined(__clang__) && !defined(__INTEL_COMPILER) && !defined(__ICL)
			// VC9's Microsoft volatile semantics give aligned LONG reads acquire
			// ordering. Keep Interlocked writes and every ownership/epoch check.
			return value;
#else
			return InterlockedCompareExchange(&value, 0, 0);
#endif
		}
		bool IsOwner() { return Read(owner) == (LONG)GetCurrentThreadId(); }
		void Clear()
		{
			capabilitiesReady=false;
			validationSupported=false;
			liveValidated=false;
			nodes.clear();
			std::fill(buckets.begin(), buckets.end(), -1);
			oldest = 0;
		}
	}

	Scope::Scope(unsigned int entries, CallbackCapabilityProvider provider) : entered(false)
	{
		const LONG thread = (LONG)GetCurrentThreadId();
		// Never modify an AI-owned table from a UI/foreign thread.
		if (Read(owner) == thread)
		{
			entered = true;
			++depth;
			Invalidate(); // A nested callback may change live state.
			return;
		}
		if (!entries || InterlockedCompareExchange(&owner, thread, 0) != 0)
			return;
		entered = true;
		depth = 1;
		capabilityProvider=provider;
		Clear();
		stats = Stats();
		stats.limit = entries > 65536 ? 65536 : entries;
		size_t bucketCount = 1;
		while (bucketCount < stats.limit * 2) bucketCount <<= 1;
		try
		{
			buckets.assign(bucketCount, -1);
		}
		catch (...)
		{
			// A throwing constructor has no destructor. Release the claimed cache
			// before propagating allocation failure to the existing caller.
			std::vector<Node>().swap(nodes);
			std::vector<int>().swap(buckets);
			depth = 0;
			capabilityProvider=NULL;
			capabilitiesReady=false;
			entered = false;
			stats = Stats();
			InterlockedExchange(&owner, 0);
			throw;
		}
		cachedEpoch = Read(epoch);
	}

	Scope::~Scope()
	{
		if (!entered)
			return;
		if (--depth)
		{
			Invalidate();
			return;
		}
		// Queries from other threads bypass throughout destruction too.
		std::vector<Node>().swap(nodes);
		std::vector<int>().swap(buckets); // Release both retained allocations in the 32-bit game.
		capabilityProvider=NULL;
		capabilitiesReady=false;
		InterlockedExchange(&owner, 0);
	}

	bool Context(long& generation)
	{
		if (!IsOwner() || depth != 1 || !stats.limit || previewSuspensionDepth || capabilitiesBuilding)
			return false;
		generation = Read(epoch);
		if (generation != cachedEpoch)
		{
			Clear();
			cachedEpoch = generation;
			++stats.invalidations;
		}
		if (!capabilityProvider) return false;
		if (liveValidated && liveValidatedEpoch == generation && capabilitiesReady)
			return capabilitiesSupported && capabilities==0;
		unsigned int liveFlags=0;
		if (!capabilityProvider(liveFlags,false))
		{
			++stats.capabilityValidationBypasses;
			// An unsupported transition must not revive retained values or proof
			// if lock/options later return without any unrelated scene signal.
			if (validationSupported || capabilitiesReady || !nodes.empty())
			{ Invalidate(); Clear(); cachedEpoch=Read(epoch); }
			return false;
		}
		validationSupported=true;
		if (!capabilitiesReady)
		{
			struct BuildingGuard
			{
				bool& flag;BuildingGuard(bool& value):flag(value){flag=true;}
				~BuildingGuard(){flag=false;}
			} building(capabilitiesBuilding);
			unsigned int flags=0;
			++stats.capabilityScans;
			const bool supported=capabilityProvider(flags,true);
			// A provider is a pure native scan, but validate the complete owner/
			// epoch/lifecycle again before publishing its bounded proof.
			if (!IsOwner() || depth!=1 || previewSuspensionDepth || Read(epoch)!=generation)
				return false;
			if (!capabilityProvider(liveFlags,false))
			{ ++stats.capabilityValidationBypasses; Invalidate(); Clear(); cachedEpoch=Read(epoch); return false; }
			stats.capabilityFlags|=flags;
			capabilities=flags;capabilitiesSupported=supported;capabilitiesReady=true;
		}
		liveValidated=true;
		liveValidatedEpoch=generation;
		return capabilitiesSupported && capabilities==0;
	}

	PreviewSuspension::PreviewSuspension(bool value):active(value)
	{
		if (active) { ++previewSuspensionDepth; Invalidate(); if(IsOwner())++stats.capabilitySuspensions; }
	}
	PreviewSuspension::~PreviewSuspension()
	{
		if (active) { --previewSuspensionDepth; Invalidate(); }
	}
	bool IsPreviewSuspended() { return previewSuspensionDepth!=0; }

	bool Lookup(const Key& key, long generation, int& value)
	{
		long current;
		if (!Context(current) || generation != current)
			return false;
		const size_t found = Find(key, Hash()(key));
		unsigned long& hits = key.values[0] == 0 ? stats.meleeHits : key.values[0] == 1 ? stats.rangedHits :
			key.values[0] == 2 ? stats.attackHits : stats.defenseHits;
		unsigned long& misses = key.values[0] == 0 ? stats.meleeMisses : key.values[0] == 1 ? stats.rangedMisses :
			key.values[0] == 2 ? stats.attackMisses : stats.defenseMisses;
		if (found == (size_t)-1)
		{
			++misses;
			return false;
		}
		++hits;
		value = nodes[found].value;
		return true;
	}

	void Store(const Key& key, long generation, int value)
	{
		long current;
		// Do not admit a result calculated across an invalidation.
		if (!Context(current) || generation != current)
			return;
		const size_t hash = Hash()(key);
		if (Find(key, hash) != (size_t)-1)
			return;
		unsigned int index;
		if (nodes.size() >= stats.limit)
		{
			index = oldest;
			Unlink(index);
			oldest = (oldest + 1) % stats.limit;
			++stats.evictions;
		}
		else
		{
			if (nodes.size() == nodes.capacity())
				nodes.reserve(std::min(stats.limit, std::max(256u, (unsigned int)nodes.size() * 2)));
			index = (unsigned int)nodes.size();
			nodes.push_back(Node());
		}
		Node& node = nodes[index];
		node.key = key;
		node.value = value;
		node.hash = hash;
		Link(index);
		if (nodes.size() > stats.peakEntries)
			stats.peakEntries = (unsigned int)nodes.size();
	}

	void Invalidate() { InterlockedIncrement(&epoch); }
	long SceneEpoch() { return Read(epoch); }
	Stats GetStats()
	{
		if (!IsOwner())
			return Stats();
		Stats result = stats;
		result.entries = (unsigned int)nodes.size();
		return result;
	}
}
