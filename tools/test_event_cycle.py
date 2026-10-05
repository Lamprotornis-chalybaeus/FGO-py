"""Synthetic event safety/cycle regressions; no private image or device."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import test_gui_navigation
from test_gui_navigation import item
import fgoEventProgress as event
import fgoEventCycle as ec
from fgoBattleFlow import BattleFlow,BattleCycle,FlowTimeout
from fgoFlowTrace import FlowTrace
from test_battle_flow import Clock,frame


class ResourceTests(unittest.TestCase):
    def test_quartz_policy_cannot_be_enabled(self):
        with self.assertRaises(ValueError):ec.EventResourcePolicy(allowQuartz=True)
    def test_apple_confirmation_allowed(self):
        ec.QuartzGuard.check([item('恢复AP',400,200),item('黄金果实',400,300)],appleConfirm=True)
    def test_quartz_ap_restore_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('恢复AP',400,200),item('圣晶石',400,300)],appleConfirm=True)
    def test_quartz_use_confirmation_without_ap_word_is_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('是否使用圣晶石？',400,200),item('黄金果实',400,300)],appleConfirm=True)
    def test_quartz_revive_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('复活',400,200),item('Saint Quartz',400,300)])
    def test_mixed_selector_only_explicit_apple(self):
        apple=item('白银果实',400,300)
        labels=[item('AP不足',400,200),apple,item('圣晶石',400,400)]
        ec.QuartzGuard.check(labels,appleOption=apple)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check(labels)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check(labels,appleOption=labels[-1])
    def test_mixed_confirmation_never_allowed(self):
        apple=item('黄金果实',400,300)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('恢复AP 是否使用',400,200),apple,item('圣晶石',400,400)],appleOption=apple)
    def test_low_confidence_quartz_still_blocked(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('恢复AP',400,200),item('圣晶石',400,300,score=.2)],appleConfirm=True)
    def test_quartz_awarded_in_nonresource_story_is_not_consumption(self):
        ec.QuartzGuard.check([item('奖励 圣晶石',400,300)])
    def test_reward_choice_is_not_story_default(self):
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('请选择奖励',400,300)])
    def test_apple_policy_disabled_never_inputs(self):
        runner=object.__new__(ec.EventRunner);runner.policy=ec.EventResourcePolicy(allowApples=False)
        with patch.object(ec.fgoDevice.device,'touch') as touch:
            with self.assertRaises(ec.ScriptStop):runner.restoreAp()
            touch.assert_not_called()


class BoundaryTests(unittest.TestCase):
    def scenario(self,states,boundary):
        clock=Clock();index=[0];inputs=[]
        def read():
            f=frame(states[index[0]])
            f.getBattleResultPage=lambda:'REWARDS' if f.isBattleFinished() else None
            return f
        def press(key):inputs.append(key);index[0]=min(index[0]+1,len(states)-1)
        flow=BattleFlow(read,clock,clock=clock,trace=FlowTrace(clock=clock))
        cycle=BattleCycle(Mock(press=press),flow)
        try:obs=cycle.settleBattleResult(boundary=boundary);error=None
        except ec.ScriptStop as e:obs=None;error=e
        return obs,error,inputs
    def test_result_to_positive_event_boundary(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','UNKNOWN'],lambda d:not d.isBattleFinished())
        self.assertIsNone(error);self.assertEqual(obs.state,ec.S.UNKNOWN);self.assertEqual(inputs,[' '])
    def test_unknown_cannot_finish_without_positive_event_proof(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','UNKNOWN'],lambda d:False)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[' '])
    def test_positive_callback_does_not_mask_defeat(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','DEFEATED'],lambda d:True)
        self.assertIsInstance(error,FlowTimeout);self.assertEqual(inputs,[' '])
    def test_original_continue_boundary_retained(self):
        obs,error,inputs=self.scenario(['BATTLE_RESULT','CONTINUE'],None)
        self.assertIsNone(error);self.assertEqual(obs.state,ec.S.CONTINUE)


class SharedEventCycleTests(unittest.TestCase):
    def runCycle(self,defeated=False):
        from test_battle_cycle import Scenario
        scenario=Scenario(defeated=defeated);scenario.state='FRIEND'
        runner=ec.EventRunner(ec.EventResourcePolicy(allowApples=False),ledger=Mock())
        runner.main.battleClass=scenario.battle
        flow=BattleFlow(scenario.read,scenario,clock=scenario,trace=FlowTrace(clock=scenario))
        names={'FRIEND':'support','FORMATION':'formation','TURN_BEGIN':'battle','BATTLE_RESULT':'battle_result','QUEST_READY':'event_map','CONTINUE':'continue','DEFEATED':'battle_defeated'}
        labels=[item('开始任务',900,550)]
        runner.read=lambda:(scenario.read(),labels,names.get(scenario.state,'unknown'))
        with patch.object(runner.main,'makeFlow',return_value=flow),patch.object(ec.nav,'labels',return_value=labels),patch.object(ec,'schedule',scenario),patch.object(ec.kernel,'schedule',scenario),patch.object(ec.kernel.XDetect,'region','CN'),patch.object(ec.kernel.friendImg,'flush',return_value=False),patch.object(ec.fgoDevice.device,'touch',side_effect=lambda pos,**kw:scenario.press('8')),patch.object(ec.fgoDevice.device,'press',side_effect=scenario.press):
            try:runner.runBattle();error=None
            except ec.ScriptStop as e:error=e
        return runner,scenario,error
    def test_event_uses_complete_shared_support_formation_battle_settlement(self):
        runner,scenario,error=self.runCycle()
        self.assertIsNone(error)
        self.assertEqual(scenario.actions,[('FRIEND','8'),('FORMATION',' '),('BATTLE_RESULT',' '),('ADD_FRIEND','X'),('CONTINUE','F')])
        self.assertEqual((runner.main.startedBattles,runner.main.completedAttempts,runner.main.wins,runner.main.defeats),(1,1,1,0))
    def test_first_event_defeat_counts_once_and_sends_no_revive(self):
        runner,scenario,error=self.runCycle(True)
        self.assertIsNotNone(error)
        self.assertEqual((runner.main.startedBattles,runner.main.completedAttempts,runner.main.wins,runner.main.defeats),(1,1,0,1))
        self.assertFalse(any(state=='DEFEATED' for state,key in scenario.actions))


class EventContractTests(unittest.TestCase):
    def test_weekly_update_notice_closes_not_opens_mission_panel(self):
        labels=[item('御主任务已更新。',490,280),item('来挑战最新的御主任务吧。',415,315),item('关闭',400,550,w=80),item('前往御主任务界面',720,550)]
        self.assertEqual(ec.weeklyUpdateInfoClose(labels),(440,562))
        self.assertIsNone(ec.weeklyUpdateInfoClose(labels[1:]))
    def test_persistent_startup_notice_does_not_reclick(self):
        labels=[item('御主任务已更新。',490,280),item('来挑战最新的御主任务吧。',415,315),item('关闭',400,550,w=80),item('前往御主任务界面',720,550)]
        clock=Clock();runner=object.__new__(ec.EventRunner);runner.clock=clock
        runner.read=Mock(return_value=(Mock(),labels,'unknown'));runner.touch=Mock()
        with patch.object(ec,'schedule',clock),patch.object(ec,'startupInfoClose',return_value=(440,562)),patch.object(ec.nav,'terminalHomeCN',return_value=False):
            with self.assertRaises(FlowTimeout):runner.openMap()
        runner.touch.assert_called_once()
    def test_sdk_guide_only_closes_verified_corner_not_shop_tiles_or_checkbox(self):
        labels=[item('游玩指引',30,170),item('最新情报',30,245),item('查找攻略',30,320),item('本月不再提示',40,650)]
        d=Mock();d._crop.return_value=__import__('numpy').zeros((54,54,3),dtype='uint8')
        with patch.object(ec.OCR.EN,'ocr_single_line',return_value=('x',.94)):
            self.assertEqual(ec.guideInfoClose(d,labels),(1246,34))
            self.assertIsNone(ec.guideInfoClose(d,labels[:2]))
        with patch.object(ec.OCR.EN,'ocr_single_line',return_value=('x',.84)):
            self.assertIsNone(ec.guideInfoClose(d,labels))
    def test_promotion_description_is_only_dismissible_not_reward_selection(self):
        labels=[item('开幕前夕纪念活动',580,110),item('举办中！',760,140),item('可从5种素材中任选其一',650,240),item('举办时间：2026年10月4日',550,490),item('关闭',600,550,w=80)]
        self.assertEqual(ec.promotionalInfoClose(labels),(640,562))
        ec.QuartzGuard.check(labels,dismissNotice=True)
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check(labels)
        self.assertIsNone(ec.promotionalInfoClose(labels+[item('兑换',800,550)]))
        with self.assertRaises(ec.ScriptStop):ec.QuartzGuard.check([item('请选择奖励',400,300)],dismissNotice=True)
    def test_login_reward_notice_only_dismisses_already_awarded_information(self):
        labels=[item('连续登录奖励',530,120),item('※请在礼物盒中领取。',540,480),item('获得了第1日的登录奖励！',530,455),item('关闭',600,550,w=80)]
        self.assertEqual(ec.loginRewardInfoClose(labels),(640,562))
        self.assertIsNone(ec.loginRewardInfoClose(labels+[item('请选择奖励',400,300)]))
        self.assertIsNone(ec.loginRewardInfoClose(labels[:2]+labels[3:]))
    def test_event_login_notice_does_not_click_summon_advertisement(self):
        labels=[item('开幕纪念登录奖励',530,150),item('请在礼物盒中领取。',540,480),item('已获得第8次的登录奖励！',530,445),item('关闭',600,550,w=80),item('推荐召唤',980,550)]
        self.assertEqual(ec.loginRewardInfoClose(labels),(640,562))
        runner=object.__new__(ec.EventRunner)
        with patch.object(ec.fgoDevice.device,'touch') as touch:
            with self.assertRaises(ec.ScriptStop):runner.touch(labels,(1050,570),'wrong',dismissNotice=True)
            touch.assert_not_called()
    def test_bulletin_title_alone_does_not_authorize_close(self):
        self.assertIsNone(ec.announcementClose(Mock(),[item('游戏公告',550,15)]))
    def test_bulletin_requires_independent_glyph_two_scale(self):
        d=Mock();d._crop.side_effect=lambda box:__import__('numpy').zeros((20,30,3),dtype='uint8')
        labels=[item('游戏公告',550,15),item('X',1220,10,w=50,score=.76)]
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('游戏公告',.96)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('x',.86),('x',.87)]):
            self.assertEqual(ec.announcementClose(d,labels),(1245,22))
        with patch.object(ec.OCR.ZHS,'ocr_single_line',return_value=('游戏公告',.96)),patch.object(ec.OCR.EN,'ocr_single_line',side_effect=[('x',.86),('x',.84)]):
            self.assertIsNone(ec.announcementClose(d,labels))
    def test_ledger_atomic_reload_never_executes_input(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(ec.fgoDevice.device,'touch') as touch:
            path=Path(folder)/'ledger.json';ec.ProgressLedger(path).append('node',title='synthetic')
            loaded=ec.ProgressLedger(path)
            self.assertEqual(loaded.data['records'][0]['title'],'synthetic');touch.assert_not_called()
            self.assertFalse(path.with_suffix('.tmp').exists())
    def test_start_confirmation_requires_phrase_and_unique_controls(self):
        labels=[item('是否开始关卡？',400,200),item('开始',800,500),item('取消',400,500)]
        self.assertTrue(event._isStartQuestConfirmation(labels))
        self.assertFalse(event._isStartQuestConfirmation(labels+[item('开始',900,500)]))
    def test_authorized_confirmation_touches_once_then_observes(self):
        labels=[item('是否开始关卡？',400,200),item('开始',800,500),item('取消',400,500)]
        runner=object.__new__(ec.EventRunner);runner.touch=Mock();runner.wait=Mock(return_value=(None,[],'story'))
        runner.handleTransition(None,labels,'start_confirmation')
        runner.touch.assert_called_once();runner.wait.assert_called_once()
    def test_plain_confirm_not_a_start_producer(self):
        labels=[item('是否购买？',400,200),item('开始',800,500),item('取消',400,500)]
        runner=object.__new__(ec.EventRunner);runner.touch=Mock()
        with self.assertRaises(ec.ScriptStop):runner.handleTransition(None,labels,'start_confirmation')
        runner.touch.assert_not_called()
    def test_actual_node_restriction_does_not_authorize_team_change(self):
        labels=[item('序幕 Goodbye 池田屋',760,130),item('AP5',760,200),item('编制需符合要求',640,220)]
        node=event.findNextMainQuest(labels)
        self.assertTrue(node['restrictions'])
        runner=ec.EventRunner(ec.EventResourcePolicy(),ledger=Mock())
        self.assertEqual(runner.main.teamIndex,0);self.assertFalse(runner.main.autoFormation)
    def test_unparsed_mission_has_no_invented_requirement(self):
        self.assertIsNone(ec.MissionRequirement.parse('未完成任务条件'))
    def test_explicit_mission_requirement_is_not_quest_mapping(self):
        r=ec.MissionRequirement.parse('任务 12 需要击败 10 个 骷髅')
        self.assertEqual((r.mission,r.kind,r.target,r.count),('12','击败','骷髅',10))
    def test_unapproved_legacy_api_does_not_call_authorized_runner(self):
        with patch.object(ec.EventRunner,'run') as run,patch.object(event.XDetect,'region','JP'):
            event.progress()
            run.assert_not_called()


if __name__=='__main__':unittest.main()
