from __future__ import annotations

from app.data.database.components import ComponentType
from app.data.database.database import DB
from app.data.database.skill_components import SkillComponent, SkillTags
from app.engine import (action, banner, combat_calcs, engine, equations,
                        image_mods, item_funcs, item_system, skill_system,
                        target_system)
from app.engine.game_state import game
from app.engine.objects.unit import UnitObject
from app.utilities import utils, static_random


class DoNothing(SkillComponent):
    nid = 'do_nothing'
    desc = 'does nothing'
    tag = SkillTags.CUSTOM

    expose = ComponentType.Int
    value = 1

class LostOnEndNextCombat(SkillComponent):
    nid = 'lost_on_end_next_combat'
    desc = "Remove after subsequent combat"
    tag = SkillTags.CUSTOM

    expose = (ComponentType.MultipleOptions)

    value = [["NumberOfCombats (X)", "2", 'Number of combats before expiration'],["LostOnSelf (T/F)", "T", 'Lost after self combat (e.g. vulnerary)'],["LostOnAlly (T/F)", "T", 'Lost after combat with an ally'],["LostOnEnemy (T/F)", "T", 'Lost after combat with an enemy'],["LostOnSplash (T/F)", "T", 'Lost after combat if using an AOE item']]
    
    def init(self, skill):
        self.skill.data['combats'] = self.values.get('NumberOfCombats (X)', '2')

    @property
    def values(self) -> Dict[str, str]:
        return {value[0]: value[1] for value in self.value}

    def post_combat(self, playback, unit, item, target, mode):
        from app.engine import skill_system
        remove_skill = False
        if self.values.get('LostOnSelf (T/F)', 'T') == 'T':
            if unit == target:
                val = int(self.skill.data['combats']) - 1
                action.do(action.SetObjData(self.skill, 'combats', val))
                if int(self.skill.data['combats']) <= 0:
                    remove_skill = True

        if self.values.get('LostOnAlly (T/F)', 'T') == 'T':
            if target:
                if skill_system.check_ally(unit, target):
                    val = int(self.skill.data['combats']) - 1
                    action.do(action.SetObjData(self.skill, 'combats', val))
                    if int(self.skill.data['combats']) <= 0:
                        remove_skill = True
        if self.values.get('LostOnEnemy (T/F)', 'T') == 'T':
            if target:
                if skill_system.check_enemy(unit, target):
                    val = int(self.skill.data['combats']) - 1
                    action.do(action.SetObjData(self.skill, 'combats', val))
                    if int(self.skill.data['combats']) <= 0:
                        remove_skill = True
        if self.values.get('LostOnSplash (T/F)', 'T') == 'T':
            if not target:
                val = int(self.skill.data['combats']) - 1
                action.do(action.SetObjData(self.skill, 'combats', val))
                if int(self.skill.data['combats']) <= 0:
                    remove_skill = True

        if remove_skill:
            action.do(action.RemoveSkill(unit, self.skill))

    def on_end_chapter(self, unit, skill):
        action.do(action.RemoveSkill(unit, self.skill))

class FullMiracle(SkillComponent):
    nid = 'full_miracle'
    desc = "Unit will not die after combat, but will instead be resurrected with full hp"
    tag = SkillTags.CUSTOM

    def cleanup_combat(self, playback, unit, item, target, mode):
        if unit.get_hp() <= 0:
            action.do(action.SetHP(unit, unit.get_max_hp()))
            game.death.miracle(unit)
            action.do(action.TriggerCharge(unit, self.skill))
            
class VariableMiracle(SkillComponent):
    nid = 'variable_miracle'
    desc = "If started combat with >% max hp, cannot be reduced below 1 HP."
    tag = SkillTags.CUSTOM
    expose = ComponentType.Float
    value = 0.5
    miracle_activates = False
    miracle_activated = False
    
    def start_combat(self, playback, unit, item, target, mode):
        if unit.get_hp() >= unit.get_max_hp() * self.value:
            self.miracle_activates = True

    def after_take_strike(self, actions, playback, unit, item, target, mode, attack_info, strike):
        if self.miracle_activates:
            for act in reversed(actions):
                if isinstance(act, action.ChangeHP) and -act.num >= act.old_hp and act.unit == unit:
                    act.num = -act.old_hp + 1
                    self.miracle_activated = True
                    self.miracle_activates = False

        if self.miracle_activated:
            actions.append(action.TriggerCharge(unit, self.skill))
            self.miracle_activated = False
            
class NihiledBy(SkillComponent):
    nid = 'nihiled_by'
    desc = "Skill does not work against a holder of this other skill"
    tag = SkillTags.CUSTOM

    expose = (ComponentType.List, ComponentType.Skill)
    value = []

    ignore_conditional = True
    _condition = True

    def pre_combat(self, playback, unit, item, target, mode):
        all_target_nihils = set(self.value)
        for skill in target.skills:
            if skill.nid in all_target_nihils:
                self._condition = False
                return
        self._condition = True

    def post_combat(self, playback, unit, item, target, mode):
        self._condition = True

    def condition(self, unit, item):
        return self._condition

    def test_on(self, playback, unit, item, target, mode):
        self.pre_combat(playback, unit, item, target, mode)

    def test_off(self, playback, unit, item, target, mode):
        self._condition = True