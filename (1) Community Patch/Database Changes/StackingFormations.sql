-- Counts are read from StackingConfig.xml. Extra slots are optional, preserving
-- early recruitment when siege technology or strategic resources are absent.
-- The assault readiness policy separately requires real siege for fortifications.
CREATE TEMP TABLE Stacking_FormationRoles(Formation TEXT, Role TEXT, Position TEXT, Setting TEXT);
INSERT INTO Stacking_FormationRoles VALUES
('MUFORMATION_SMALL_CITY_ATTACK_FORCE','UNITAI_CITY_BOMBARD','MUPOSITION_BOMBARD','AIAssaultSmallExtraSiegeSlots'),
('MUFORMATION_SMALL_CITY_ATTACK_FORCE','UNITAI_ATTACK','MUPOSITION_FRONT_LINE','AIAssaultSmallExtraFrontSlots'),
('MUFORMATION_BASIC_CITY_ATTACK_FORCE','UNITAI_CITY_BOMBARD','MUPOSITION_BOMBARD','AIAssaultBasicExtraSiegeSlots'),
('MUFORMATION_BASIC_CITY_ATTACK_FORCE','UNITAI_ATTACK','MUPOSITION_FRONT_LINE','AIAssaultBasicExtraFrontSlots'),
('MUFORMATION_BIGGER_CITY_ATTACK_FORCE','UNITAI_CITY_BOMBARD','MUPOSITION_BOMBARD','AIAssaultBiggerExtraSiegeSlots'),
('MUFORMATION_BIGGER_CITY_ATTACK_FORCE','UNITAI_ATTACK','MUPOSITION_FRONT_LINE','AIAssaultBiggerExtraFrontSlots');

INSERT INTO MultiUnitFormation_SlotEntries
    (MultiUnitFormationType, PrimaryUnitType, SecondaryUnitType, MultiUnitPositionType, RequiredSlot)
SELECT roles.Formation, roles.Role,
       CASE WHEN roles.Role='UNITAI_ATTACK' THEN 'UNITAI_DEFENSE' ELSE roles.Role END,
       roles.Position, 0
FROM Stacking_FormationRoles roles
JOIN Stacking_Settings settings ON settings.Name=roles.Setting
CROSS JOIN (SELECT 0 AS n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3
            UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7) numbers
WHERE numbers.n < MIN(8,MAX(0,settings.Value))
  AND EXISTS (SELECT 1 FROM Stacking_Settings WHERE Name='Enabled' AND Value>0)
  AND EXISTS (SELECT 1 FROM MultiUnitFormations WHERE Type=roles.Formation);
DROP TABLE Stacking_FormationRoles;
