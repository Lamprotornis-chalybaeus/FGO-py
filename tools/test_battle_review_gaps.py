"""Review regressions: safe template input, turn edges and parent deadlines."""
import unittest
from unittest.mock import Mock,patch
from test_battle_cycle import kernel
from test_battle_flow import Clock,frame
from fgoBattleFlow import BattleFlow,BattleCycle,BattleFlowState as S,FlowTimeout
from fgoFlowTrace import FlowTrace

class TemplateInputTests(unittest.TestCase):
    def choose(self,matches,*,region='CN',continued=False,exitState='FORMATION'):
        clock=Clock();state=['FRIEND'];reads=iter(matches);last=matches[-1];inputs=[];found=[]
        def read():
            d=frame(state[0]);d.isFriendListEnd=lambda:True
            def find(img):
                p=next(reads,last);found.append(p);return p
            d.findFriend=find;kernel.Detect.cache=d;return d
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock))
        store=Mock();store.flush.return_value=True;store.orderedItems.return_value=[('confirmed',object())]
        def touch(pos,**kwargs):inputs.append((pos,kwargs));state[0]=exitState
        with patch.object(kernel.XDetect,'region',region),patch.object(kernel,'schedule',clock),patch.object(kernel,'friendImg',store),patch.object(kernel.fgoDevice.device,'touch',side_effect=touch):
            try:result=kernel.Main(friendPolicy='strict',friendMaxRefresh=0).chooseFriend(flow,continued=continued);error=None
            except FlowTimeout as e:result=None;error=e
        return inputs,result,error,found
    def test_transient_template_never_clicks(self):
        inputs,_,error,_=self.choose([(650,300),None])
        self.assertEqual(inputs,[]);self.assertIsInstance(error,FlowTimeout)
    def test_stable_cn_template_confirms_fresh_frames_then_one_80ms_input(self):
        inputs,result,error,found=self.choose([(650,300)]*4)
        self.assertIsNone(error);self.assertEqual(inputs,[((650,300),{'duration':.08})]);self.assertGreaterEqual(len(found),4)
        self.assertEqual(result.state,S.FORMATION)
    def test_different_card_position_never_clicks(self):
        inputs,_,error,_=self.choose([(650,300),(650,480)])
        self.assertEqual(inputs,[]);self.assertIsInstance(error,FlowTimeout)
    def test_non_cn_preserves_single_match_and_default_duration(self):
        for region in ('JP','NA','TW'):
            inputs,_,error,found=self.choose([(650,300),None],region=region)
            self.assertIsNone(error);self.assertEqual(inputs,[((650,300),{})]);self.assertEqual(len(found),1)
    def test_continue_cn_template_can_exit_to_turn_without_another_start(self):
        inputs,result,error,_=self.choose([(650,300)]*4,continued=True,exitState='TURN_BEGIN')
        self.assertIsNone(error);self.assertEqual(result.state,S.TURN_BEGIN);self.assertEqual(len(inputs),1)
    def test_initial_template_does_not_admit_direct_battle(self):
        inputs,_,error,_=self.choose([(650,300)]*4,exitState='TURN_BEGIN')
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(len(inputs),1)
    def test_non_cn_continue_does_not_admit_direct_battle(self):
        inputs,_,error,_=self.choose([(650,300)],region='JP',continued=True,exitState='TURN_BEGIN')
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(len(inputs),1)

class TurnEpisodeTests(unittest.TestCase):
    def runBattle(self,reader,turn,clock):
        battle=kernel.Battle(turnClass=lambda:turn);battle.flow=BattleFlow(reader,clock,clock=clock,trace=FlowTrace(clock=clock))
        with patch.object(kernel,'schedule',clock):result=battle()
        return battle,result
    def test_attack_held_two_seconds_executes_one_turn(self):
        clock=Clock();turns=[]
        battle,result=self.runBattle(lambda:frame('TURN_BEGIN' if clock.now<2 else 'BATTLE_RESULT'),turns.append,clock)
        self.assertTrue(result);self.assertEqual(turns,[1]);self.assertEqual(battle.turn,1)
    def test_nested_skill_animation_does_not_rearm_same_turn(self):
        clock=Clock();turns=[];state=['TURN_BEGIN'];holder={}
        def turn(n):
            turns.append(n);state[0]='UNKNOWN';holder['battle'].flow.observe()
            state[0]='TURN_BEGIN';holder['battle'].flow.observe()
        battle=kernel.Battle(turnClass=lambda:turn);holder['battle']=battle
        battle.flow=BattleFlow(lambda:frame(state[0] if clock.now<2 else 'BATTLE_RESULT'),clock,clock=clock,trace=FlowTrace(clock=clock))
        with patch.object(kernel,'schedule',clock):self.assertTrue(battle())
        self.assertEqual(turns,[1])
    def test_final_cards_departure_then_new_attack_increments_once(self):
        clock=Clock();turns=[];states=iter(['TURN_BEGIN','TURN_BEGIN','UNKNOWN','LOADING','TURN_BEGIN','TURN_BEGIN','BATTLE_RESULT'])
        _,result=self.runBattle(lambda:frame(next(states,'BATTLE_RESULT')),turns.append,clock)
        self.assertTrue(result);self.assertEqual(turns,[1,2])
    def test_result_directly_ends_without_another_turn(self):
        clock=Clock();turns=[];states=iter(['TURN_BEGIN','BATTLE_RESULT'])
        _,result=self.runBattle(lambda:frame(next(states,'BATTLE_RESULT')),turns.append,clock)
        self.assertTrue(result);self.assertEqual(turns,[1])
    def test_defeat_directly_ends_without_revival(self):
        class DefeatClock(Clock):
            def checkDefeated(self):pass
        clock=DefeatClock();turns=[];states=iter(['TURN_BEGIN','DEFEATED'])
        _,result=self.runBattle(lambda:frame(next(states,'DEFEATED')),turns.append,clock)
        self.assertFalse(result);self.assertEqual(turns,[1])

class PreparationDeadlineTests(unittest.TestCase):
    def prepare(self,initial,*,existing=10,continued=False,fail=False):
        clock=Clock();flow=BattleFlow(lambda:frame(initial),clock,clock=clock,trace=FlowTrace(clock=clock));flow.deadline=existing
        main=Mock()
        main.chooseFriend.side_effect=lambda **kw:flow.waitForFlowState({S.TURN_BEGIN},timeout=180,transition_name='direct repeat test',allowed_intermediate={S.FRIEND})
        main.prepareFormation.side_effect=lambda f:f.waitForFlowState({S.TURN_BEGIN},timeout=180,transition_name='formation test',allowed_intermediate={S.FORMATION})
        error=None
        try:result=BattleCycle(main,flow).prepare()
        except FlowTimeout as e:result=None;error=e
        return flow,clock,main,result,error
    def test_parent_remaining_ten_seconds_caps_formation_and_restores_deadline(self):
        flow,clock,_,_,error=self.prepare('FORMATION')
        self.assertIsInstance(error,FlowTimeout);self.assertLess(clock.now,10.3);self.assertEqual(flow.deadline,10)
    def test_parent_remaining_ten_seconds_caps_direct_support_wait(self):
        flow,clock,_,_,error=self.prepare('FRIEND')
        self.assertIsInstance(error,FlowTimeout);self.assertLess(clock.now,10.3);self.assertEqual(flow.deadline,10)
    def test_no_existing_deadline_limits_entire_child_to_180_and_restores_none(self):
        flow,clock,_,_,error=self.prepare('FORMATION',existing=None)
        self.assertIsInstance(error,FlowTimeout);self.assertLess(clock.now,180.3);self.assertIsNone(flow.deadline)
    def test_170_seconds_spent_before_formation_leaves_only_ten(self):
        clock=Clock();state=['FRIEND'];flow=BattleFlow(lambda:frame(state[0]),clock,clock=clock);main=Mock()
        def friend(**kw):clock.now=170;state[0]='FORMATION';flow.observe()
        main.chooseFriend.side_effect=friend
        main.prepareFormation.side_effect=lambda f:f.waitForFlowState({S.TURN_BEGIN},timeout=180,transition_name='formation',allowed_intermediate={S.FORMATION})
        with self.assertRaises(FlowTimeout):BattleCycle(main,flow).prepare()
        self.assertLess(clock.now,180.3);self.assertIsNone(flow.deadline)
    def test_170_seconds_spent_before_direct_repeat_leaves_only_ten(self):
        clock=Clock();state=['CONTINUE'];flow=BattleFlow(lambda:frame(state[0]),clock,clock=clock);main=Mock()
        def press(key):clock.now=170;state[0]='FRIEND'
        main.press.side_effect=press
        def friend(**kw):
            self.assertTrue(kw['continued'])
            flow.waitForFlowState({S.TURN_BEGIN},timeout=180,transition_name='direct',allowed_intermediate={S.FRIEND})
        main.chooseFriend.side_effect=friend
        with self.assertRaises(FlowTimeout):BattleCycle(main,flow).prepare()
        self.assertLess(clock.now,180.3);self.assertIsNone(flow.deadline)
    def test_success_restores_existing_parent_deadline(self):
        flow,clock,_,result,error=self.prepare('TURN_BEGIN',existing=200)
        self.assertTrue(result);self.assertIsNone(error);self.assertEqual(flow.deadline,200)
    def test_prepare_restores_deadline_on_non_flow_exception(self):
        clock=Clock();flow=BattleFlow(lambda:frame('FORMATION'),clock,clock=clock);flow.deadline=200
        main=Mock();main.prepareFormation.side_effect=ValueError('failure')
        with self.assertRaises(ValueError):BattleCycle(main,flow).prepare()
        self.assertEqual(flow.deadline,200)

if __name__=='__main__':unittest.main()
