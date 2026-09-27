-- Strings deliberately reference final database Types, not transient IDs.
-- VP and later modmods may add replacement units after CP loads these rows.
CREATE TABLE IF NOT EXISTS Stacking_Settings (Name TEXT PRIMARY KEY NOT NULL, Value INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS Stacking_Technologies (TechType TEXT PRIMARY KEY NOT NULL, CapacityBonus INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS Stacking_UnitCombatRoles (UnitCombatType TEXT NOT NULL, Role TEXT NOT NULL, Value INTEGER NOT NULL, PRIMARY KEY (UnitCombatType, Role));
CREATE TABLE IF NOT EXISTS Stacking_UnitClassRoles (UnitClassType TEXT NOT NULL, Role TEXT NOT NULL, Value INTEGER NOT NULL, PRIMARY KEY (UnitClassType, Role));
CREATE TABLE IF NOT EXISTS Stacking_UnitRoles (UnitType TEXT NOT NULL, Role TEXT NOT NULL, Value INTEGER NOT NULL, PRIMARY KEY (UnitType, Role));
CREATE TABLE IF NOT EXISTS Stacking_PromotionRoles (PromotionType TEXT NOT NULL, Role TEXT NOT NULL, Value INTEGER NOT NULL, PRIMARY KEY (PromotionType, Role));
CREATE TABLE IF NOT EXISTS Stacking_BuildingClassProtection (BuildingClassType TEXT PRIMARY KEY NOT NULL, ProtectionPercent INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS Stacking_BuildingProtection (BuildingType TEXT PRIMARY KEY NOT NULL, ProtectionPercent INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS Stacking_CollateralDomains (DomainType TEXT PRIMARY KEY NOT NULL, Enabled INTEGER NOT NULL);
