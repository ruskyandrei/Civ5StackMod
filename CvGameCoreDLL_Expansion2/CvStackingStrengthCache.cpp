#include "CvGameCoreDLLPCH.h"
#include "CvStackingStrengthCache.h"
#include <unordered_map>
#include <deque>
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
		typedef std::tr1::unordered_map<Key, int, Hash> Table;
		Table table;
		// Node references survive rehash. FIFO stores references, not duplicate keys.
		std::deque<const Key*> order;
		volatile LONG owner = 0, epoch = 0;
		LONG cachedEpoch = 0;
		unsigned int depth = 0;
		Stats stats = {};
		LONG Read(volatile LONG& value) { return InterlockedCompareExchange(&value, 0, 0); }
		bool IsOwner() { return Read(owner) == (LONG)GetCurrentThreadId(); }
		void Clear()
		{
			order.clear();
			table.clear();
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
		std::deque<const Key*>().swap(order);
		Table().swap(table); // Also release retained buckets in the 32-bit game.
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
		Table::const_iterator found = table.find(key);
		unsigned long& hits = key.values[0] == 0 ? stats.meleeHits : stats.rangedHits;
		unsigned long& misses = key.values[0] == 0 ? stats.meleeMisses : stats.rangedMisses;
		if (found == table.end())
		{
			++misses;
			return false;
		}
		++hits;
		value = found->second;
		return true;
	}

	void Store(const Key& key, long generation, int value)
	{
		long current;
		// Do not admit a result calculated across an invalidation.
		if (!Context(current) || generation != current || table.find(key) != table.end())
			return;
		if (table.size() >= stats.limit)
		{
			Table::iterator victim = table.find(*order.front());
			order.pop_front();
			table.erase(victim);
			++stats.evictions;
		}
		std::pair<Table::iterator, bool> added = table.insert(std::make_pair(key, value));
		order.push_back(&added.first->first);
		if (table.size() > stats.peakEntries)
			stats.peakEntries = (unsigned int)table.size();
	}

	void Invalidate() { InterlockedIncrement(&epoch); }
	Stats GetStats()
	{
		if (!IsOwner())
			return Stats();
		Stats result = stats;
		result.entries = (unsigned int)table.size();
		return result;
	}
}
