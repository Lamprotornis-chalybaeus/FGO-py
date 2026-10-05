"""Bounded main-story campaign, indexed farming and empirical Mission solver.

Pipeline states describe internal work, not invented UI producers. EventRunner
owns screenshots/input and the shared BattleCycle; this layer has no battle AI.
"""
import re,time
from fgoAutomation import automationOwner
from fgoSchedule import ScriptStop,schedule
import fgoEventProgress as event
from fgoEventEngine import CampaignState,EventFarmTask,EventProfile,missionValue
from fgoEventQuest import EventQuestLocator

def completeProof(items):
    if event._unsafeEventOverlay(items):return None
    explicit=[i for i in items if i.score>=.85 and event._text(i).rstrip('。.!！') in ('活动主线剧情已完成','活动主线已通关','主线剧情全部完成','活动主剧情已完成')]
    return str(explicit[0].text) if len(explicit)==1 else None

class EventCampaignRunner:
    def __init__(self,runner,index,evidence,profile):
        if index.eventKey!=evidence.eventKey or profile.eventKey!=index.eventKey:raise ValueError('Campaign event scope mismatch')
        self.runner=runner;self.index=index;self.evidence=evidence;self.profile=profile
        self.locator=EventQuestLocator(runner,index);self.state=CampaignState.ENTER_EVENT
        self.solved=set();self.experiments=0;self.startEntries=runner.newBattleEntries
    def phase(self,state,**fields):
        self.state=state;self.runner.ledger.append('campaign_phase',state=state.value,**fields)
    def observeMissions(self,required):
        """Collect every reliably readable card along the bounded target route.

        Coverage is explicitly partial, never a fabricated complete 100-Mission
        scan. Two fresh identical observations admit secondary cards; seekMission
        independently requires three full proofs for the blocking requirement.
        """
        self.phase(CampaignState.MISSION_LIST,mission=required)
        counts={};observed={};raw=self.runner.read
        def read():
            d,items,state=raw()
            if state=='mission_list':
                numbers=[int(re.search(r'\d+',event._text(i))[0]) for i in items if i.score>=.85 and re.fullmatch(r'编号\d+',event._text(i))]
                for n in set(numbers):
                    card=event.findMissionCard(items,n)
                    if card:
                        key=(n,event.normalizeText(card['condition']),card['progress'])
                        counts[key]=counts.get(key,0)+1
                        if counts[key]>=2:observed[str(n)]={k:card[k] for k in ('mission','condition','progress')}
            return d,items,state
        self.runner.read=read
        try:
            self.runner.missionListTop()
            d,items,state,card=self.runner.seekMission(required)
            observed[str(required)]={k:card[k] for k in ('mission','condition','progress')}
        finally:self.runner.read=raw
        self.runner.ledger.append('mission_snapshot',coverage='readable cards along top/target lookup route; partial',missions=observed)
        return observed,(d,items,state),card
    def missionMenu(self):
        d,items,state=self.runner.read()
        if state=='mission_list':return d,items,state
        if state=='mission_gate' and event.findLockedEventMission(items):return self.runner.openMissionRequirements(d,items)
        if state not in ('event_map','event_world_map'):raise ScriptStop('Mission menu has no positive map origin')
        previous=None
        for _ in range(3):
            d,items,state=self.runner.read()
            controls=[i for i in items if i.score>=.85 and event._text(i)=='活动报酬' and i.center[0]>1100 and i.center[1]<100]
            if state not in ('event_map','event_world_map') or len(controls)!=1:raise ScriptStop('Mission menu control unproven')
            pos=controls[0].center
            if previous and max(abs(a-b) for a,b in zip(previous,pos))>6:raise ScriptStop('Mission menu control unstable')
            previous=pos
        self.runner.touch(items,pos,'campaign_open_missions')
        return self.runner.wait({'mission_list'},timeout=30)
    def drain(self,outcome):
        end=self.runner.clock()+180;steps=0
        while self.runner.clock()<end:
            d,items,state=outcome
            if state in ('event_map','event_world_map','mission_gate'):
                return self.runner.wait({'event_map','event_world_map','mission_gate'},timeout=30,accept=lambda d,i,s:s!='mission_gate' or event.findLockedEventMission(i) is not None)
            steps+=1
            if steps>24:raise ScriptStop('Event receipt/story boundary budget exhausted')
            if state in ('reward_receipt','item_receipt'):outcome=self.runner.handleRewardReceipt(d,items)
            elif state=='item_detail':outcome=self.runner.closeItemDetail(d,items)
            elif state=='event_tutorial':outcome=self.runner.advanceTutorial(d,items)
            elif state=='item_information':outcome=self.runner.closeMissionItemInfo(d,items)
            elif state=='quest_information':outcome=self.runner.closeQuestInformation(d,items)
            elif state in ('story','story_skip_confirmation','start_confirmation'):outcome=self.runner.handleTransition(d,items,state,deadline=end)
            elif state in ('battle_result','friend_request','continue'):outcome=self.runner.runBattle(questKind='free')
            else:raise ScriptStop('Unhandled event boundary '+state)
        raise ScriptStop('Event boundary hard deadline exhausted')
    def battleQuest(self,quest):
        self.phase(CampaignState.FREE_QUEST,quest=quest.key)
        fresh=self.locator.locate(quest)
        originLock=event.findLockedEventMission(self.runner.last[1]) if self.runner.last else None
        def fadingOrigin(d,items,state):
            current=event.findLockedEventMission(items)
            return originLock is not None and current is not None and current['mission']==originLock['mission']
        outcome=self.runner.wait({'start_confirmation','story','support','formation','ap_empty'},timeout=30,blockedIntermediate=fadingOrigin)
        start=self.runner.newBattleEntries;end=self.runner.clock()+240
        while self.runner.clock()<end:
            d,items,state=outcome
            if state in ('support','formation','battle'):
                self.phase(CampaignState.FARMING,quest=fresh.key)
                outcome=self.runner.runBattle(questKind='free');break
            if state in ('start_confirmation','story','story_skip_confirmation'):outcome=self.runner.handleTransition(d,items,state,deadline=end)
            elif state=='ap_empty':
                self.runner.restoreAp();outcome=self.runner.read()
            elif state=='special_formation_offer':outcome=self.runner.configureSpecialFormation(d,items)
            elif state=='formation_restriction_notice':outcome=self.runner.closeFormationRestrictionNotice(d,items)
            else:raise ScriptStop('Free Quest preparation unproven: '+state)
        else:raise ScriptStop('Free Quest preparation hard deadline')
        outcome=self.drain(outcome)
        if self.runner.newBattleEntries!=start+1:raise ScriptStop('Experiment did not have exactly one actual battle entry')
        entry=self.runner.activeEntryId
        wins=[r for r in self.runner.records() if r.get('kind')=='battle_outcome' and r.get('entryId')==entry]
        if len(wins)!=1 or wins[0].get('won') is not True:raise ScriptStop('Experiment outcome not uniquely proved win')
        self.runner.ledger.append('event_free_complete',quest=fresh.key,entryId=entry,normal=wins[0]['mode']=='normal',AP=self.runner.ap(outcome[0]))
        return fresh,entry,outcome
    def solve(self,requirement):
        self.phase(CampaignState.MISSION_GATE,mission=requirement['mission'])
        mission=requirement['mission']
        self.missionMenu();before,origin,card=self.observeMissions(mission)
        for attempt in range(40):
            done,total=missionValue(card)
            if done==total:
                self.phase(CampaignState.REWARD,mission=mission)
                outcome=self.runner.claimCompletedMission(mission)
                self.solved.add(mission)
                self.runner.ledger.append('campaign_mission_solved',mission=mission,progress=card['progress'])
                if outcome[2]=='mission_list':outcome=self.runner.returnFromMissions(outcome[0],outcome[1])
                return self.drain(outcome)
            if origin[2]!='mission_list':raise ScriptStop('Mission baseline no longer on proved list')
            self.runner.returnFromMissions(origin[0],origin[1])
            d,items,state=self.runner.read()
            if state=='event_world_map':self.runner.openNextArea()
            quests=self.locator.scan(complete=not bool(self.index.available()))
            choices=self.evidence.rank(quests,card)
            if not choices:raise ScriptStop('No untried or positively mapped available candidate; experiment budget stops')
            self.runner.ledger.append('mission_experiment_intent',quest=choices[0].key,mission=mission,before=before,startedEntryIds=sorted(self.runner._entryIds))
            quest,entry,outcome=self.battleQuest(choices[0])
            self.missionMenu();after,origin,nextCard=self.observeMissions(mission)
            row=self.evidence.record(quest,entry,before,after,won=True,source='one actual won Free Quest; independent before/after readable Mission snapshots')
            self.experiments+=1
            self.runner.ledger.append('mission_experiment',entryId=entry,quest=quest.key,deltaVector=row['deltaVector'],mission=mission)
            before=after;card=nextCard
        raise ScriptStop('Mission experiment hard budget reached')
    def farm(self,task):
        if not isinstance(task,EventFarmTask):raise TypeError('EventFarmTask required')
        quest=self.index.entries.get(task.quest)
        if quest is None:raise ScriptStop('Farm quest not indexed')
        if task.untilComplete:
            self.missionMenu();_,_,card=self.observeMissions(task.mission)
            # Mission mode may learn/choose alternatives only through solve.
            # An explicitly fixed quest must already have measured positive effect.
            effect=self.evidence.effects(task.mission,card['condition']).get(quest.key,{})
            if not effect.get('positiveSamples'):raise ScriptStop('Mission farm requires measured positive quest effect')
            return self.solve(card)
        outcome=None
        for _ in range(task.runs):outcome=self.battleQuest(quest)[2]
        return outcome
    def run(self,*,maxNodes=100,maxNewEntries=120,hardSeconds=7200):
        end=self.runner.clock()+hardSeconds;nodes=0
        with automationOwner.claim():
            try:
                while self.runner.clock()<end and nodes<maxNodes:
                    if self.runner.newBattleEntries-self.startEntries>=maxNewEntries:raise ScriptStop('Campaign new-entry budget reached')
                    d,items,state=self.runner.read();proof=completeProof(items)
                    if proof:
                        for _ in range(2):
                            d,items,state=self.runner.read()
                            if completeProof(items)!=proof:raise ScriptStop('Event completion evidence transient')
                        self.profile.completeEvidence.append(proof);self.phase(CampaignState.EVENT_COMPLETE)
                        return self.report('event_complete')
                    self.phase(CampaignState.MAIN_NODE)
                    beforeNodes=self.runner.completed
                    result=self.runner.run(beforeNodes+1)
                    nodes+=self.runner.completed-beforeNodes
                    if result['state']=='mission_gate':self.solve(result['requirement'])
                    elif result['state']=='limit_reached':continue
                    else:return self.report('blocked',reason=result.get('message',result['state']))
                return self.report('bounded_stop',reason='node/time budget reached')
            except ScriptStop as error:
                self.runner.evidence(error);return self.report('blocked',reason=str(error),errorType=type(error).__name__)
    def report(self,state,**fields):
        values=self.runner.report(state,**fields)
        values.update(campaignState=self.state.value,solvedMissions=sorted(self.solved),experiments=self.experiments,indexEntries=len(self.index.entries),locatorMetrics=self.locator.metrics,goal=self.profile.goal,mainStoryComplete=state=='event_complete')
        return values
