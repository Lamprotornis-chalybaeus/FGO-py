"""Offline event safeguards: mock inputs only, no connected game or private PNGs."""
import os
from pathlib import Path
import runpy
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')
with patch.object(threading.Thread,'start',return_value=None):
    env=runpy.run_path(str(Path(__file__).with_name('test_gui_navigation.py')))
event=env['event'];item=env['item'];FakeDetect=env['FakeDetect']


class EventModalGuardTests(unittest.TestCase):
    def setUp(self):
        self.frame=FakeDetect()
        self.missions=[item('活动任务列表',400,100),item('任务 No.2 已完成',350,250,300),item('领取',1120,250,80)]

    def overlay(self,text):
        return self.missions+[item(text,510,360,240),item('确定',740,535,80),item('取消',400,535,80)]

    def runProgress(self,items,**options):
        with patch.object(event.XDetect,'region','CN'),\
             patch.object(event,'Detect',return_value=self.frame),\
             patch.object(event,'_readScreen',return_value=items),\
             patch.object(event,'_openEventMap',return_value=(self.frame,items)),\
             patch.object(event,'_waitClassified',return_value=(self.frame,items,event.classifyEventState(items))),\
             patch.object(event.schedule,'sleep',return_value=None),\
             patch.object(event.fgoDevice.device,'touch') as touch:
            result=event.progress(**options)
        return result,touch

    def test_reward_choice_overlay_never_clicks_background_row(self):
        for text in ('请选择奖励','选择奖励','奖励选择','任选一项奖励','二选一奖励'):
            for claim in (False,True):
                with self.subTest(text=text,autoClaim=claim):
                    result,touch=self.runProgress(self.overlay(text),autoClaim=claim)
                    self.assertEqual(result['state'],'unsafe_modal')
                    self.assertIn('没有点击背景',result['message'])
                    touch.assert_not_called()

    def test_generic_confirmation_never_clicks_background_row(self):
        result,touch=self.runProgress(self.overlay('是否领取该奖励？'),autoClaim=True)
        self.assertEqual(result['state'],'unsafe_modal');touch.assert_not_called()

    def test_ap_purchase_confirmations_never_click_background(self):
        for text in ('AP不足','是否恢复AP？','是否购买道具？','使用苹果恢复AP','使用圣晶石恢复AP'):
            with self.subTest(text=text):
                result,touch=self.runProgress(self.overlay(text),autoClaim=True)
                self.assertEqual(result['state'],'unsafe_modal');touch.assert_not_called()

    def test_overlay_precedes_background_support_and_formation_flags(self):
        for flag in ('choose_friend','formation','battle_result'):
            with self.subTest(flag=flag):
                self.assertEqual(event.classifyEventState(self.overlay('请选择奖励'),{flag:True}),'unsafe_modal')

    def test_known_start_confirmation_retains_its_safe_stop(self):
        screen=[item('是否开始关卡？',500,350,260),item('取消',400,540,80),item('开始',800,540,80)]
        result,touch=self.runProgress(screen)
        self.assertEqual(result['state'],'start_confirmation');touch.assert_not_called()

    def test_mission_page_requires_unique_confident_activity_top_title(self):
        self.assertTrue(event._missionListConfirmed(self.missions))
        for title in (item('任务列表',400,100),item('活动任务列表',400,100,score=.79),item('活动任务列表',400,250),item('已达成的任务',900,20)):
            with self.subTest(title=title.text,box=title.box,score=title.score):
                self.assertFalse(event._missionListConfirmed([title]+self.missions[1:]))
        self.assertFalse(event._missionListConfirmed(self.missions+[item('活动任务',800,20)]))

    def test_direct_reward_helper_rechecks_overlay_and_title(self):
        for screen in (self.overlay('请选择奖励'),self.overlay('是否领取该奖励？'),[item('任务列表',400,100)]+self.missions[1:]):
            with self.subTest(screen=[i.text for i in screen]),patch.object(event.fgoDevice.device,'touch') as touch:
                _,_,result=event._claimMissionRewards(self.frame,screen)
                self.assertIn(result['state'],('unsafe_modal','mission_blocked'));touch.assert_not_called()

    def test_reward_loop_stops_on_new_overlay_after_one_legitimate_claim(self):
        screen=self.overlay('请选择奖励')
        with patch.object(event.fgoDevice.device,'touch') as touch,patch.object(event,'_waitClassified',return_value=(self.frame,screen,'unsafe_modal')):
            _,_,result=event._claimMissionRewards(self.frame,self.missions)
        self.assertEqual(result['state'],'unsafe_modal');self.assertEqual(result['claimed'],1)
        touch.assert_called_once_with((1160,262))

    def test_return_button_is_not_clicked_through_overlay(self):
        screen=[item('活动任务列表',400,100),item('返回',40,35)]+self.overlay('请选择奖励')[3:]
        with patch.object(event.fgoDevice.device,'touch') as touch:
            _,_,result=event._claimMissionRewards(self.frame,screen)
        self.assertEqual(result['state'],'unsafe_modal');touch.assert_not_called()

    def test_low_confidence_action_targets_are_rejected(self):
        for func,title,x,y in ((event.findSkipButton,'SKIP',1000,30),(event.findMissionListEntry,'活动任务',800,120),(event._missionReturnButton,'返回',40,35),(event.findEventBattleStart,'开始任务',900,540),(event.findBattleProgressButton,'下一步',900,540)):
            with self.subTest(action=func.__name__):
                self.assertIsNone(func([item(title,x,y,score=.79)]))
                self.assertIsNotNone(func([item(title,x,y,score=.8)]))
        weak=self.missions[:2]+[item('领取',1120,250,80,score=.79)]
        self.assertIsNone(event.findClaimableMissionReward(weak))

    def test_low_confidence_completion_does_not_authorize_claim(self):
        weak=[self.missions[0],item('任务 No.2 已完成',350,250,300,score=.79),self.missions[2]]
        self.assertIsNone(event.findClaimableMissionReward(weak))

    def test_low_confidence_main_title_is_not_clickable(self):
        screen=[item('关卡举办时间 剩余13日',950,260,270),item('序幕「测试节点」',780,120,320,score=.79),item('AP5',780,200,60)]
        self.assertIsNone(event.findNextMainQuest(screen))

    def test_completion_negative_evidence_remains_conservative(self):
        screen=[item('关卡举办时间 剩余13日',950,260,270),item('序幕「测试节点」',780,120,320),item('AP5',780,200,60),item('已完成',650,200,100,score=.41)]
        self.assertIsNone(event.findNextMainQuest(screen))

    def test_additional_team_restrictions_stop_without_edit_or_node_click(self):
        base=[item('关卡举办时间 剩余13日',950,260,270),item('序幕「测试节点」',780,120,320),item('AP5',780,200,60)]
        for restriction in ('编制需符合要求','编队限制','限定编队','只能使用NPC从者','请使用指定编队','固定编队出击'):
            with self.subTest(restriction=restriction):
                screen=base+[item(restriction,650,220,200,score=.41)]
                candidate=event.findNextMainQuest(screen)
                self.assertEqual(candidate['restrictions'],[restriction])
                result,touch=self.runProgress(screen)
                self.assertEqual(result['state'],'blocked');self.assertIn('编队限制',result['message']);touch.assert_not_called()

    def test_dialogue_choice_stops_before_skip_even_when_skip_enabled(self):
        screen=[item('SKIP',1100,30,80),item('请选择接下来的行动',460,260,300),item('前往大门',470,355,200),item('继续等待',470,440,200),item('这段话是正在显示的剧情对话。',160,580,900)]
        with patch.object(event,'_skipStory') as skip:
            result,touch=self.runProgress(screen,storyMode=event.EVENT_STORY_SKIP)
        self.assertEqual(result['state'],'unsafe_modal');skip.assert_not_called();touch.assert_not_called()

    def test_plain_story_still_pauses_by_default(self):
        screen=[item('SKIP',1100,30,80),item('这段话是正在显示的剧情对话。',160,580,900)]
        result,touch=self.runProgress(screen)
        self.assertEqual(result['state'],'story_paused');touch.assert_not_called()


if __name__=='__main__':unittest.main()
