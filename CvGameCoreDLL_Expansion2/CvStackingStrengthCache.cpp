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
				size_t result = 0;
				for (size_t i = 0; i < sizeof(key.values) / sizeof(key.values[0]); ++i)
					result ^= (size_t)key.values[i] + 0x9e3779b9 + (result << 6) + (result >> 2);
				return result;
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
			nodes.clear();
			std::fill(buckets.begin(), buckets.end(), -1);
			oldest = 0;
		}
	}

	Scope::Scope(unsigned int entries) : entered(false)
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
		InterlockedExchange(&owner, 0);
	}

	bool Context(long& generation)
	{
		if (!IsOwner() || depth != 1 || !stats.limit)
			return false;
		generation = Read(epoch);
		if (generation != cachedEpoch)
		{
			Clear();
			cachedEpoch = generation;
			++stats.invalidations;
		}
		return true;
	}

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
