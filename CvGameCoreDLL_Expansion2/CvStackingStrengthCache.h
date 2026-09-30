#pragma once

// Exact combat-strength memoization during one tactical preview search. The
// engine scene is fixed while the GameCore lock is held; projected positions
// and wounds are arguments, not changes to live units. No data is serialized.
namespace CvStackingStrengthCache
{
	struct Key
	{
		int values[22];
		bool operator==(const Key& other) const;
	};
	struct Stats
	{
		unsigned long meleeHits, meleeMisses, rangedHits, rangedMisses;
		unsigned long attackHits, attackMisses, defenseHits, defenseMisses;
		unsigned long evictions, invalidations;
		unsigned int entries, peakEntries, limit;
	};
	class Scope
	{
	public:
		explicit Scope(unsigned int entries);
		~Scope();
	private:
		bool entered;
		Scope(const Scope&);
		Scope& operator=(const Scope&);
	};
	bool Context(long& generation);
	bool Lookup(const Key& key, long generation, int& value);
	void Store(const Key& key, long generation, int value);
	// Thread-safe invalidation only changes an epoch. Foreign UI threads never
	// touch the map. Call before releasing GameCore and on dirty danger state.
	void Invalidate();
	// Shared live-scene revision; valid even when strength caching is disabled.
	long SceneEpoch();
	Stats GetStats();
}
