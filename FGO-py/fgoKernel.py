# Stars  Cosmos Gods  Animus    Antrum       Unbirth    Anima Animusphere
# 星の形.宙の形.神の形.我の形.天体は空洞なり.空洞は虚空なり.虚空には神ありき.
# 地を照らし,空に在り,天上の座標を示せ.
# カルディアの灯よ.
# どうか今一度,旅人の標とならん事を.
# ここで,Bgo運営の敗北を宣言する!
# .        OO---O---O-o\
# .       // \ / \ / \ \\
# .      OO   O   O   O \\
# .     // \   \ /   / \ \\
# .    oO---O---O---O---O-Oo
# .     \\ /   / \   \ / //
# .      \O   O   O   O //
# .       \\ / \ / \ / //
# .        oO---O---Oo-O
# .             ^^
# .  Grand Order/Anima Animusphere
# .     冠位指定/人理保障天球
'Full-automatic FGO Script'
from fgoConst import VERSION
__version__=VERSION
__author__='hgjazhgj'
import logging,numpy,pulp,random,re,time,threading
from copy import deepcopy
from contextvars import ContextVar
import fgoDevice
from fgoAutomation import automationOwner,NETWORK_ERROR_EVENT,GUARDIAN_STOP,INPUT_OBSERVER
import fgoFriendPolicy
import fgoApRecovery
import fgoNavigation
from itertools import permutations
from functools import wraps
from fgoDetect import Detect,XDetect,OCR
from fgoFuse import fuse
from fgoImageListener import ImageListener
from fgoFriendTemplates import FriendTemplateStore
from fgoBattleFlow import BattleCycle,BattleFlow,BattleFlowState,FriendSelectionResult,FlowTimeout
from fgoFlowTrace import FlowTrace
from fgoBattleProgress import BattleProgressTracker
from fgoProgress import BattleCompleted
from fgoPaths import paths
from fgoLogging import getLogger,logit
from fgoMetadata import servantData,missionMat,missionTag,missionQuest
from fgoReishift import reishift
from fgoSchedule import ScriptStop,schedule
logger=getLogger('Kernel')

friendImg=FriendTemplateStore(paths.dataRoot/'fgoImage'/'friend')
mailImg=ImageListener('fgoImage/mail/')
mutex=threading.Lock()
def serialize(lock):
    def decorator(func):
        @wraps(func)
        def wrapper(*args,**kwargs):
            with lock,automationOwner.claim():return func(*args,**kwargs)
        return wrapper
    return decorator
def guardian(stopEvent=GUARDIAN_STOP):
    logger=logging.getLogger('Guardian')
    prev=None
    # Daemon lifecycle is explicitly interruptible; no device inputs here.
    while not stopEvent.wait(.5):
        current=XDetect.cache
        if current is None or current is prev:continue
        predicate=getattr(current,'isNetworkError',None)
        if callable(predicate) and predicate():
            NETWORK_ERROR_EVENT.set()
            logger.warning('Network error reported to automation owner')
        prev=current
threading.Thread(target=guardian,daemon=True,name='Guardian').start()
def handleNetworkError(detect):
    if not detect.isNetworkError():return False
    fgoDevice.device.press('K')
    NETWORK_ERROR_EVENT.clear()
    return True
class Farming:
    def __init__(self):
        self.logger=getLogger('Farming')
        self.stop=False
    def __call__(self):
        time.sleep(100)
        while not self.stop:
            if not fgoDevice.device.available:
                time.sleep(30)
                continue
            delay=self.run()
            time.sleep(30 if delay is None else max(0,delay)+30)
    @serialize(mutex)
    def run(self):
        from fgoFarming import farming
        try:
            return farming()
        except Exception as e:
            logger.exception(e)
            return 0
farming=Farming()
threading.Thread(target=farming,daemon=True,name='Farming').start()
def setup():
    raise NotImplementedError
    if not fgoDevice.device.isInGame():
        fgoDevice.device.launch()
        fgoNavigation.legacyWait(lambda d:d.isGameLaunch(),'game launch',60)
        guard=fgoNavigation.NavigationGuard('game announce',60)
        for _ in guard.steps():
            if Detect(1).isGameAnnounce():break
            fgoDevice.device.press('\xBB')
        fgoDevice.device.press('\x08')
    elif False:...
@serialize(mutex)
def fpSummon():
    fgoNavigation.refuseUnverifiedCNAction('友情召唤')
    for _ in fgoNavigation.NavigationGuard('legacy FP summon',300,300).steps():
        if fuse.value>=30:break
        if Detect().isSummonContinue():fgoDevice.device.perform('MK',(600,2700))
        fgoDevice.device.press('\x08')
@serialize(mutex)
def lottery():
    fgoNavigation.refuseUnverifiedCNAction('活动抽奖')
    Detect().setupLottery()
    count=0
    for _ in fgoNavigation.NavigationGuard('legacy lottery',300,300).steps():
        count=0 if Detect().isLotteryContinue()else count+1
        if count>=5:break
        for _ in range(random.randint(10,100)):fgoDevice.device.press('2')
# @serialize(mutex)
# def mining():
#     while fuse.value<30:
#         if Detect().isMining():fgoDevice.device.perform('K',(300,))
#         fgoDevice.device.perform('9Z',(300,300))
@serialize(mutex)
def mail():
    fgoNavigation.refuseUnverifiedCNAction('礼物箱处理')
    assert mailImg.flush()
    Detect().setupMailDone()
    guard=fgoNavigation.NavigationGuard('legacy mail scan',180,100)
    for _ in guard.steps():
        for _ in guard.steps():
            if not any((pos:=Detect.cache.findMail(i[1]))and(fgoDevice.device.touch(pos),True)[-1]for i in mailImg.items()):break
            guard.wait(lambda d:d.isMailDone(),'mail receipt')
        guard.progress(fgoNavigation.stableCrop(Detect.cache,(73,166,920,680)))
        fgoDevice.device.swipe((400,600),(400,200))
        if Detect().isMailListEnd():break
@serialize(mutex)
def synthesis():
    fgoNavigation.refuseUnverifiedCNAction('自动强化')
    guard=fgoNavigation.NavigationGuard('legacy synthesis',180,100)
    for _ in guard.steps():
        fgoDevice.device.perform('8',(1000,))
        for i,j in((i,j)for i in range(4)for j in range(7)):fgoDevice.device.touch((133+133*j,253+142*i),100)
        if Detect().isSynthesisFinished():break
        fgoDevice.device.perform('  KK\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB\xBB',(800,300,300,1000,150,150,150,150,150,150,150,150,150,150,150,150,150,150,150))
        for _ in guard.steps():
            if Detect().isSynthesisBegin():break
            guard.progress(fgoNavigation.stableCrop(Detect.cache))
            fgoDevice.device.press('\xBB')
@serialize(mutex)
def dailyFpSummon():
    fgoNavigation.refuseUnverifiedCNAction('每日友情召唤')
    if XDetect.region=='CN':fgoNavigation.returnRootCN()
    else:fgoNavigation.legacyWait(lambda d:d.isMainInterface(),'FP summon root')
    fgoDevice.device.perform(' Z',(1000,2000))
    fgoNavigation.legacyWait(lambda d:d.isMainInterface(),'FP summon menu')
    guard=fgoNavigation.NavigationGuard('FP summon tabs',30,30)
    for _ in guard.steps():
        if Detect(1.5).isSummonFp():break
        guard.progress(fgoNavigation.stableCrop(Detect.cache));fgoDevice.device.press('\xBC')
    fgoDevice.device.perform('\xBDJ',(800,3000))
    guard=fgoNavigation.NavigationGuard('FP summon completion',45,60)
    for _ in guard.steps():
        if Detect(.5).isSummonContinue():break
        fgoDevice.device.press(' ')
    fgoDevice.device.perform('\x67\x67',(1200,2000))
@serialize(mutex)
def dailyStorySummon():
    fgoNavigation.refuseUnverifiedCNAction('剧情召唤')
    if XDetect.region=='CN':fgoNavigation.returnRootCN()
    else:fgoNavigation.legacyWait(lambda d:d.isMainInterface(),'story summon root')
    fgoDevice.device.press(' ')
    if not Detect(1).isSummonStory():
        fgoDevice.device.perform(' \x67',(1000,2000))
        return
    fgoDevice.device.press('\xBD')
    fgoNavigation.legacyWait(lambda d:d.isMainInterface(),'story summon menu')
    fgoDevice.device.perform('GJ',(800,3000))
    for _ in fgoNavigation.NavigationGuard('story summon completion',45,60).steps():
        if Detect(.5).isSummonFinish():break
        fgoDevice.device.press(' ')
    fgoDevice.device.perform('\x67\x67',(1200,2000))
@serialize(mutex)
def summonHistory():
    fgoNavigation.refuseUnverifiedCNAction('召唤记录导航')
    Detect().setupSummonHistory()
    guard=fgoNavigation.NavigationGuard('summon history scan',120,100)
    for _ in guard.steps():
        if Detect.cache.isSummonHistoryListEnd():break
        guard.progress(fgoNavigation.stableCrop(Detect.cache,(147,157,1105,547)))
        fgoDevice.device.swipe((930,500),(930,200))
        Detect(.4).getSummonHistory()
    return{'type':'SummonHistory'}|dict(zip(('value','file'),Detect.cache.saveSummonHistory()))
@serialize(mutex)
def bench(times=20,touch=True,screenshot=True):
    if not(touch or screenshot):touch=screenshot=True
    screenshotBench=[]
    for _ in range(times*screenshot):
        begin=time.time()
        fgoDevice.device.screenshot()
        screenshotBench.append(time.time()-begin)
    touchBench=[]
    for _ in range(times*touch):
        begin=time.time()
        fgoDevice.device.press('\xBB')
        touchBench.append(time.time()-begin)
    return{
        'type':'Bench',
        'touch':(sum(touchBench)-max(touchBench)-min(touchBench))*1000/(times-2)if touch else None,
        'screenshot':(sum(screenshotBench)-max(screenshotBench)-min(screenshotBench))*1000/(times-2)if screenshot else None,
    }
@serialize(mutex)
@fgoNavigation.boundedNavigation(180)
def goto(quest):
    if XDetect.region=='CN':return fgoNavigation.gotoFreeQuestCN(tuple(quest))
    fgoNavigation.legacyWait(lambda d:d.isMainInterface(),'return to legacy menu')
    fgoDevice.device.press(' ')
    fgoDevice.device.perform(*((' ',(600,))if Detect(.6).isTerminal()else('S',(1500,))))
    reishift(quest)
    schedule.sleep(.5)
    for _ in range(4):
        if Detect(.4).isQuestListBegin():break
        fgoDevice.device.swipe((1000,200),(1000,600))
    fgoNavigation.legacyScroll(lambda d:d.isQuestFreeContains(quest[0]),'find Free Quest',(1000,600),(1000,200))
    fgoNavigation.legacyScroll(lambda d:d.isQuestFreeFirst(quest[0]),'place Free Quest',(1000,395),(1000,300))
@fgoNavigation.boundedNavigation(240)
def _weeklyMissionDetailed():
    guard=fgoNavigation.NavigationGuard('weeklyMission',240,60)
    guard.stage('WEEKLY','正在读取每周任务…')
    if XDetect.region=='CN':fgoNavigation.returnRootCN(guard)
    else:fgoNavigation.legacyWait(lambda d:d.isMainInterface(),'weekly mission home')
    fgoDevice.device.perform('B',(800,))
    guard.wait(lambda d:d.isWeeklyMission(),'weekly mission panel')
    if XDetect.region=='CN':
        detect=Detect(.2);items=fgoNavigation.labels(detect)
        tab=fgoNavigation.unique(items,'周常',(700,95,850,180))
        if not tab:guard.fail('weekly tab is not uniquely recognized')
        fgoDevice.device.touch(tab.center);schedule.sleep(.8)
    else:fgoDevice.device.perform('2N',(100,1000))
    if XDetect.region=='CN':parsed=fgoNavigation.readWeeklyRowsCN(guard)
    else:
        Detect().setupWeeklyMission()
        for _ in guard.steps():
            if Detect.cache.isWeeklyMissionListEnd():break
            guard.progress(fgoNavigation.stableCrop(Detect.cache,(603,250,1092,710)))
            fgoDevice.device.swipe((1000,600),(1000,300))
            Detect(.4).getWeeklyMission()
        parsed=Detect.cache.saveWeeklyMissionDetailed()
    rows=parsed['tasks']
    rowCompleted=sum(count<=0 for _,_,count in rows)
    recognized=max(len(rows),parsed['explicitCompleted'])
    completed=min(recognized,max(rowCompleted,parsed['explicitCompleted']))
    active=[row for row in rows if row[2]>0]
    x=[pulp.LpVariable('_'.join(str(j)for j in i),lowBound=0,cat=pulp.LpInteger)for i in missionQuest]
    prob=pulp.LpProblem('WeeklyMission',sense=pulp.LpMinimize)
    prob+=pulp.lpDot(missionMat[0],x)
    supported=unsupported=0
    for target,minion,count in active:
        coefficient=sum((j for i in target for j,k in zip(missionMat,missionTag)if i in k and(minion or'从者'in k)),numpy.zeros(missionMat.shape[1]))
        if coefficient.any():
            supported+=1
            logger.info(f'Add [{"|".join(target)}],{minion},{count}')
            prob+=pulp.lpDot(coefficient,x)>=count
        else:
            unsupported+=1
            logger.error(f'Invalid Target [{"|".join(target)}],{minion},{count}')
    if supported:
        status=prob.solve(pulp.PULP_CBC_CMD(msg=False,timeLimit=30))
        if status!=pulp.LpStatusOptimal:guard.fail('weekly quest solver did not finish optimally; no queue generated')
        objective=prob.objective.value()
        quests=[(tuple(int(i)for i in v.name.split('_')),int(v.varValue))for v in prob.variables()if v.varValue]
    else:
        objective=0
        quests=[]
    fgoDevice.device.press('\x67')
    if XDetect.region=='CN':guard.wait(lambda d:fgoNavigation.classify(d)=='ROOT_CATEGORY','weekly panel close')
    recognitionError=not rows and not parsed['explicitCompleted']
    report={
        'type':'WeeklyMission',
        'recognized':recognized,
        'completed':completed,
        'supported':supported,
        'unsupported':unsupported,
        'entries':len(quests),
        'expectedAp':round(objective or 0),
        'quests':quests,
        'recognitionError':recognitionError,
    }
    logger.info(f'WeeklyMission summary: recognized={recognized} completed={completed} supported={supported} unsupported={unsupported} entries={len(quests)} expectedAP={report["expectedAp"]} malformed={parsed["malformed"]}')
    logger.debug(f'WeeklyMission OCR lines: {parsed["lines"]!r}')
    if recognitionError:logger.error('WeeklyMission OCR did not yield task rows; inspect OCR lines above')
    return report

@serialize(mutex)
def weeklyMissionDetailed():return _weeklyMissionDetailed()

def weeklyMission():return weeklyMissionDetailed()['quests']
_activeBattleFlow=ContextVar('active_battle_flow',default=None)
class BattlePhaseEnded(Exception):
    def __init__(self,state):self.state=state
def recoverSkillFailure():
    flow=_activeBattleFlow.get()
    if flow:return flow.action('skill_cast_failed_recover',lambda:fgoDevice.device.press('J'))
    fgoDevice.device.press('J')
def waitForTurnBegin(reason,timeout=45):
    flow=_activeBattleFlow.get() or BattleFlow(lambda:Detect(0,0),schedule,
        trace=FlowTrace(root=paths.logRoot/'flow'),network=handleNetworkError)
    S=BattleFlowState
    observation=flow.waitForFlowState({S.TURN_BEGIN,S.BATTLE_RESULT,S.DEFEATED},
        timeout=timeout,transition_name=reason,on_skill_error=lambda:fgoDevice.device.press('J'))
    if observation.state!=S.TURN_BEGIN:raise BattlePhaseEnded(observation.state)
    return flow.detect
class ClassicTurn:
    skillInfo=[[[0,0,0,7],[0,0,0,7],[0,0,0,7]],[[0,0,0,7],[0,0,0,7],[0,0,0,7]],[[0,0,0,7],[0,0,0,7],[0,0,0,7]],[[0,0,0,7],[0,0,0,7],[0,0,0,7]],[[0,0,0,7],[0,0,0,7],[0,0,0,7]],[[0,0,0,7],[0,0,0,7],[0,0,0,7]]]
    houguInfo=[[1,7],[1,7],[1,7],[1,7],[1,7],[1,7]]
    masterSkill=[[0,0,0,7],[0,0,0,7],[0,0,0,0,7]]
    def __init__(self):
        ClassicTurn.friendInfo=[[[-1,-1,-1,-1],[-1,-1,-1,-1],[-1,-1,-1,-1]],[-1,-1]]
        self.stage=0
        self.stageTurn=0
        self.servant=[0,1,2]
        self.orderChange=[0,1,2,3,4,5]
        self.countDown=[[[0,0,0],[0,0,0],[0,0,0]],[0,0,0]]
    def __call__(self,turn):
        self.stage,self.stageTurn=[t:=Detect(.2).getStage(),1+self.stageTurn*(self.stage==t)]
        self.friend=[Detect.cache.isServantFriend(i)for i in range(3)]
        if turn==1:
            Detect.cache.setupServantDead(self.friend)
            self.stageTotal=Detect.cache.getStageTotal()
            self.servant=[6 if self.servant[i]>=6 or Detect.cache.getFieldServantClassRank(i)is None else self.servant[i]for i in range(3)]
        else:
            for i in(i for i in range(3)if self.servant[i]<6 and Detect.cache.isServantDead(i,self.friend[i])):
                self.servant[i]=max(self.servant)+1
                self.countDown[0][i]=[0,0,0]
        logger.info(f'Turn {turn} Stage {self.stage} StageTurn {self.stageTurn} {self.servant}')
        if self.stageTurn==1:Detect.cache.setupEnemyGird()
        self.dispatchSkill()
        fgoDevice.device.perform(' ',(2100,))
        fgoDevice.device.perform(self.selectCard(),(300,300,2300,1300,6000))
    def dispatchSkill(self):
        self.countDown=[[[max(0,j-1)for j in i]for i in self.countDown[0]],[max(0,i-1)for i in self.countDown[1]]]
        while(s:=[(self.getSkillInfo(i,j,3),0,(i,j))for i in range(3)if self.servant[i]<6 for j in range(3)if self.countDown[0][i][j]==0 and(t:=self.getSkillInfo(i,j,0))and min(t,self.stageTotal)<<8|self.getSkillInfo(i,j,1)<=self.stage<<8|self.stageTurn and Detect.cache.isSkillReady(i,j)]+[(self.masterSkill[i][-1],1,(i,))for i in range(3)if self.countDown[1][i]==0 and self.masterSkill[i][0]and min(self.masterSkill[i][0],self.stageTotal)<<8|self.masterSkill[i][1]<=self.stage<<8|self.stageTurn]):
            _,cast,arg=min(s,key=lambda x:x[0])
            [self.castServantSkill,self.castMasterSkill][cast](*arg)
            fgoDevice.device.perform('\x08',(700,))
            waitForTurnBegin('skill/master animation',timeout=45)
            Detect(.5)
    @logit(logger,logging.INFO)
    def selectCard(self):return''.join((lambda hougu,sealed,color,resist,critical:(fgoDevice.device.perform('\x67\x68\x69\x64\x65\x66'[numpy.argmax([Detect.cache.getEnemyHp(i)for i in range(6)])],(500,))if any(hougu)or self.stageTurn==1 else 0,['678'[i]for i in sorted((i for i in range(3)if hougu[i]),key=lambda x:self.getHouguInfo(x,1))]+['12345'[i]for i in sorted(range(5),key=(lambda x:-color[x]*resist[x]*(not sealed[x])*(1+critical[x])))]if any(hougu)else(lambda group:['12345'[i]for i in(lambda choice:choice+tuple({0,1,2,3,4}-set(choice)))(logger.debug('cardRank'+','.join(('  'if i%5 else'\n')+f'({j}, {k:5.2f})'for i,(j,k)in enumerate(sorted([(card,(lambda colorChain,firstCardBonus:sum((firstCardBonus+[1.,1.2,1.4][i]*color[j])*(1+critical[j])*resist[j]*(not sealed[j])for i,j in enumerate(card))+(not any(sealed[i]for i in card))*(4.8*colorChain+(firstCardBonus+1.)*(3 if colorChain else 1.8)*(len({group[i]for i in card})==1)*resist[card[0]]))(len({color[i]for i in card})==1,.3*(color[card[0]]==1.1)))for card in permutations(range(5),3)],key=lambda x:-x[1]))))or max(permutations(range(5),3),key=lambda card:(lambda colorChain,firstCardBonus:sum((firstCardBonus+[1.,1.2,1.4][i]*color[j])*(1+critical[j])*resist[j]*(not sealed[j])for i,j in enumerate(card))+(not any(sealed[i]for i in card))*(4.8*colorChain+(firstCardBonus+1.)*(3 if colorChain else 1.8)*(len({group[i]for i in card})==1)*resist[card[0]]))(len({color[i]for i in card})==1,.3*(color[card[0]]==1.1))))])(Detect.cache.getCardGroup()))[1])([self.servant[i]<6 and j and(t:=self.getHouguInfo(i,0))and self.stage>=min(t,self.stageTotal)for i,j in enumerate(Detect().isHouguReady())],Detect.cache.isCardSealed(),[[.8,1.,1.1][i]for i in Detect.cache.getCardColor()],[[1.,1.7,.6][i]for i in Detect.cache.getCardResist()],[i/10 for i in Detect.cache.getCardCriticalRate()]))
    def getSkillInfo(self,pos,skill,arg):return self.friendInfo[0][skill][arg]if self.friend[pos]and self.friendInfo[0][skill][arg]>=0 else self.skillInfo[self.orderChange[self.servant[pos]]][skill][arg]
    def getHouguInfo(self,pos,arg):return self.friendInfo[1][arg]if self.friend[pos]and self.friendInfo[1][arg]>=0 else self.houguInfo[self.orderChange[self.servant[pos]]][arg]
    def castServantSkill(self,pos,skill):
        fgoDevice.device.press(('ASD','FGH','JKL')[pos][skill])
        if Detect(.7).isSkillNone():
            logger.warning(f'Skill {pos} {skill} Disabled')
            self.countDown[0][pos][skill]=999
        elif Detect(.7).isSkillCastFailed():
            self.countDown[pos][skill]=1
            recoverSkillFailure()
        elif t:=Detect.cache.getSkillTargetCount():fgoDevice.device.perform(['3333','2244','3234'][t-1][self.getSkillInfo(pos,skill,2)],(300,))
    def castMasterSkill(self,skill):
        self.countDown[1][skill]=15
        fgoDevice.device.perform('Q'+'WER'[skill],(300,300))
        if self.masterSkill[skill][2]:
            if skill==2 and self.masterSkill[2][3]:
                if self.masterSkill[2][2]-1 not in self.servant or self.masterSkill[2][3]-1 in self.servant:return fgoDevice.device.perform('\xBB',(300,))
                p=self.servant.index(self.masterSkill[2][2]-1)
                fgoDevice.device.perform(('TYUIOP'[p],'TYUIOP'[self.masterSkill[2][3]-max(self.servant)+1],'Z'),(300,300,2600))
                self.orderChange[self.masterSkill[2][2]-1],self.orderChange[self.masterSkill[2][3]-1]=self.orderChange[self.masterSkill[2][3]-1],self.orderChange[self.masterSkill[2][2]-1]
                fgoDevice.device.perform('\x08',(2300,))
                waitForTurnBegin('skill/master animation',timeout=45)
                self.friend=[Detect(.5).isServantFriend(0),Detect.cache.isServantFriend(1),Detect.cache.isServantFriend(2)]
                Detect.cache.setupServantDead(self.friend)
            elif t:=Detect(.5).getSkillTargetCount():fgoDevice.device.perform(['3333','2244','3234'][t-1][self.masterSkill[skill][2]],(300,))
class Turn:
    def __init__(self):
        self.stage=0
        self.stageTurn=0
        self.countDown=[[[0,0,0],[0,0,0],[0,0,0]],[0,0,0]]
    def __call__(self,turn):
        self.stage,self.stageTurn=[t:=Detect(.2).getStage(),1+self.stageTurn*(self.stage==t)]
        if turn==1:
            Detect.cache.setupServantDead()
            self.stageTotal=Detect.cache.getStageTotal()
            self.servant=[(lambda x:(x,)+servantData.get(x,(0,0,0,0,(0,0),((0,0),(0,0),(0,0)))))(Detect.cache.getFieldServant(i))for i in range(3)]
        else:
            for i in(i for i in range(3)if Detect.cache.isServantDead(i)):
                self.servant[i]=(lambda x:(x,)+servantData.get(x,(0,0,0,0,(0,0),((0,0),(0,0),(0,0)))))(Detect.cache.getFieldServant(i))
                self.countDown[0][i]=[0,0,0]
        logger.info(f'Turn {turn} Stage {self.stage} StageTurn {self.stageTurn} {[i[0]for i in self.servant]}')
        if self.stageTurn==1:self.enemy=[2,0,5][Detect.cache.setupEnemyGird()]
        self.enemy=[Detect.cache.getEnemyHp(i)for i in range(6)]
        self.dispatchSkill()
        fgoDevice.device.perform(' ',(2100,))
        fgoDevice.device.perform(self.selectCard(),(300,300,2300,1300,6000))
    def dispatchSkill(self):
        self.countDown=[[[max(0,j-1)for j in i]for i in self.countDown[0]],[max(0,i-1)for i in self.countDown[1]]]
        while skill:=[(0,i,j)for i in range(3)for j in range(3)if not self.countDown[0][i][j]and self.servant[i][0]and self.servant[i][6][j][0]and Detect.cache.isSkillReady(i,j)]: # +[(1,i)for i in range(3)if self.countDown[1][i]==0]:
            for i in skill:
                if i[0]==0:
                    match self.servant[i[1]][6][i[2]]:
                        case 1,_:
                            self.castServantSkill(i[1],i[2],i[1]+1)
                            continue
                        case 2,p:
                            np=[Detect.cache.getFieldServantNp(i)if self.servant[i][0]else 100 for i in range(3)]
                            match p:
                                case 0:
                                    if any(i<100 for i in np):
                                        self.castServantSkill(i[1],i[2],0)
                                        continue
                                case 1:
                                    target=numpy.argmin(np)
                                    if np[target]<100:
                                        self.castServantSkill(i[1],i[2],target+1)
                                        continue
                                case 2:
                                    np[i[1]]=100
                                    if any(i<100 for i in np):
                                        self.castServantSkill(i[1],i[2],0)
                                        continue
                                case 3|4:
                                    if self.stageTurn>1:
                                        self.castServantSkill(i[1],i[2],0)
                                        continue
                                case 5:
                                    if np[i[1]]<100:
                                        self.castServantSkill(i[1],i[2],i[1]+1)
                                        continue
                                case _:
                                    self.castServantSkill(i[1],i[2],0)
                                    continue
                        case 3,p:
                            np=[Detect.cache.getFieldServantNp(i)if self.servant[i][0]else 0 for i in range(3)]
                            match p:
                                case 0|3|4:
                                    if any(i>=100 for i in np):
                                        self.castServantSkill(i[1],i[2],0)
                                        continue
                                case 1:
                                    target=numpy.argmax(np)
                                    if np[target]>=100:
                                        self.castServantSkill(i[1],i[2],target+1)
                                        continue
                                case 2:
                                    np[i[1]]=0
                                    if any(i>=100 for i in np):
                                        self.castServantSkill(i[1],i[2],0)
                                        continue
                                case 5:
                                    if np[i[1]]>=100:
                                        self.castServantSkill(i[1],i[2],i[1]+1)
                                        continue
                                case _:
                                    self.castServantSkill(i[1],i[2],0)
                                    continue
                        case 4|5|6,_:
                            self.castServantSkill(i[1],i[2],0)
                            continue
                        case 7,p:
                            hp=[Detect.cache.getFieldServantHp(i)if self.servant[i][0]else 999999 for i in range(3)]
                            match p:
                                case 0:
                                    if any(i<6600 for i in hp):
                                        self.castServantSkill(i[1],i[2],0)
                                        continue
                                case 1:
                                    target=numpy.argmin(hp)
                                    if hp[target]<6600:
                                        self.castServantSkill(i[1],i[2],target+1)
                                        continue
                                case 2:
                                    hp[i[1]]=999999
                                    if any(i<6600 for i in hp):
                                        self.castServantSkill(i[1],i[2],0)
                                        continue
                                case 3|4:
                                    self.castServantSkill(i[1],i[2],0)
                                    continue
                                case 5:
                                    if hp[i[1]]<6600:
                                        self.castServantSkill(i[1],i[2],i[1]+1)
                                        continue
                                case _:
                                    self.castServantSkill(i[1],i[2],0)
                                    continue
                        case 8,_:
                            if any((lambda x:x[1]and x[0]==x[1])(Detect.cache.getEnemyNp(i))for i in range(6)):
                                self.castServantSkill(i[1],i[2],i[1]+1)
                                continue
                        case 9,_:
                            if any((lambda x:x[1]and x[0]==x[1])(Detect.cache.getEnemyNp(i))for i in range(6))or Detect.cache.getFieldServantHp(i[1])<3300:
                                self.castServantSkill(i[1],i[2],i[1]+1)
                                continue
                    self.countDown[0][i[1]][i[2]]=1
                else:...
    @logit(logger,logging.INFO)
    def selectCard(self):
        color,sealed,hougu,np,resist,critical,group=Detect().getCardColor()+[i[5][1]for i in self.servant],Detect.cache.isCardSealed(),Detect.cache.isHouguReady(),[Detect.cache.getFieldServantNp(i)<100 for i in range(3)],[[1,1.7,.6][i]for i in Detect.cache.getCardResist()],[i/10 for i in Detect.cache.getCardCriticalRate()],[next(j for j,k in enumerate(self.servant)if k[0]==i)for i in Detect.cache.getCardServant([i[0] for i in self.servant if i[0]])]+[0,1,2]
        houguTargeted,houguArea,houguSupport=[[j for j in range(3)if hougu[j]and self.servant[j][0]and self.servant[j][5][0]==i]for i in range(3)]
        houguArea=houguArea if self.stage==self.stageTotal or sum(i>0 for i in self.enemy)>1 and sum(self.enemy)>12000 else[]
        houguTargeted=houguTargeted if self.stage==self.stageTotal or max(self.enemy)>23000+8000*len(houguArea)else[]
        hougu=[i+5 for i in houguSupport+houguArea+houguTargeted]
        if self.stageTurn==1 or houguTargeted or self.enemy[self.target]==0:
            self.target=numpy.argmax(self.enemy)
            fgoDevice.device.perform('\x67\x68\x69\x64\x65\x66'[self.target],(500,))
        self.enemy=[max(0,i-18000*len(houguArea))for i in self.enemy]
        if any(self.enemy)and self.enemy[self.target]==0:self.target=next(i for i in range(5,-1,-1)if self.enemy[i])
        for _ in houguTargeted:
            self.enemy[self.target]=max(0,self.enemy[self.target]-48000)
            if any(self.enemy)and self.enemy[self.target]==0:self.target=next(i for i in range(5,-1,-1)if self.enemy[i])
        def evaluate(card):return(lambda chainError:(lambda colorChain:(lambda firstBonus:
                sum(
                    ((.3*bool(firstBonus&4)+.1*bool(firstBonus&1)+[1.,1.2,1.4][i]*[1,.8,1.1][color[j]])*(1+min(1,critical[j]+.2*bool(firstBonus&2)))+bool(colorChain==2))*resist[j]*(not sealed[j])
                    for i,j in enumerate(card)if j<5
                )
                +4*(len([i for i in self.enemy if i])>1)*(self.enemy[self.target]<20000)*sum(bool(i)for i in numpy.diff([group[i]for i in card if i<5]))
                +(1.8 if colorChain==-1 else 3)*(not chainError and len({group[i]for i in card})==1)*resist[card[0]]
                +2.3*(colorChain==0)*len({group[i]for i in card if i<5 and np[group[i]]})
                +3*(colorChain==1)
            )(7 if colorChain==3 else 1<<color[0]))(-1 if chainError else{(0,):0,(1):1,(2,):2,(0,1,2):3}.get(tuple(set(color[i]for i in card)),-1)))(any(sealed[i]for i in card if i<5))
        card=list(max(permutations(range(5),3-len(hougu)),key=lambda x:evaluate(hougu+list(x))))
        return''.join(['12345678'[i]for i in hougu+card+list({0,1,2,3,4}-set(card))])
    def castServantSkill(self,pos,skill,target):
        fgoDevice.device.press(('ASD','FGH','JKL')[pos][skill])
        if Detect(.7).isSkillNone():
            logger.warning(f'Skill {pos} {skill} Disabled')
            self.countDown[0][pos][skill]=999
            fgoDevice.device.press('\x08')
        elif Detect.cache.isSkillCastFailed():
            logger.warning(f'Skill {pos} {skill} Cast Failed')
            self.countDown[0][pos][skill]=1
            recoverSkillFailure()
        elif t:=Detect.cache.getSkillTargetCount():fgoDevice.device.perform(['3333','2244','3234'][t-1][f-5 if(f:=self.servant[pos][6][skill][1])in{6,7,8}else target]+'\x08',(300,700))
        else:fgoDevice.device.perform('\x08',(700,))
        waitForTurnBegin('skill/master animation',timeout=45)
        Detect(.5)
    def castMasterSkill(self,skill,target):
        self.countDown[1][skill]=15
        fgoDevice.device.perform('Q'+'WER'[skill],(300,300))
        if t:=Detect(.4).getSkillTargetCount():fgoDevice.device.perform(['3333','2244','3234'][t-1][target],(300,))
        waitForTurnBegin('skill/master animation',timeout=45)
        Detect(.5)
class Battle:
    def __init__(self,turnClass=Turn):
        self.turn=0
        self.turnProc=turnClass()
    totalTimeout=30*60
    unknownTimeout=60
    phaseHardTimeout=180
    def __call__(self):
        self.start=time.time();self.defeated=False
        self.flow=getattr(self,'flow',None) or BattleFlow(lambda:Detect(0,0),schedule,
            trace=FlowTrace(root=paths.logRoot/'flow'),network=handleNetworkError)
        flow=self.flow;S=BattleFlowState
        deadline=flow.clock()+self.totalTimeout
        tracker=BattleProgressTracker(clock=flow.clock,stall_timeout=self.unknownTimeout,phase_hard_timeout=self.phaseHardTimeout)
        previousDeadline=flow.deadline;flow.deadline=deadline
        token=_activeBattleFlow.set(flow)
        inputToken=INPUT_OBSERVER.set(flow.deviceInput)
        previousContext=flow.trace.battle_context
        progressLogged=-float('inf')
        def progressEvent(event):
            nonlocal progressLogged
            flow.trace.battle_context=tracker.snapshot()
            if event and (event not in {'loading_progress','unknown_visual_progress'} or flow.clock()-progressLogged>=5):
                flow.trace.battleProgress(event,tracker.snapshot());progressLogged=flow.clock()
        # Only outer observations after the complete skill/card phase may
        # rearm. Nested skill animations cannot create another AI turn.
        turnArmed=True
        unknownDeparture=0;departureCapture=None
        try:
            while flow.clock()<deadline:
                observation=flow.observe();state=observation.state
                progressEvent(tracker.observe(observation,flow.detect))
                if state not in {S.BATTLE_RESULT,S.DEFEATED} and tracker.hard_expired():
                    flow.fail(FlowTimeout,'TIMEOUT battle phase',{S.TURN_BEGIN,S.BATTLE_RESULT,S.DEFEATED},flow.clock()-tracker.phase_started,from_state=tracker.last_positive_state)
                if state==S.UNKNOWN and not turnArmed:
                    capture=observation.capture_sequence
                    if capture is not None and capture!=departureCapture:
                        unknownDeparture=unknownDeparture+1 if departureCapture is not None and capture==departureCapture+1 else 1
                        departureCapture=capture
                        if unknownDeparture>=2:turnArmed=True
                else:
                    unknownDeparture=0;departureCapture=None
                    if state==S.LOADING:turnArmed=True
                if state==S.TURN_BEGIN and turnArmed:
                    turnArmed=False
                    unknownDeparture=0;departureCapture=None
                    self.turn+=1;progressEvent(tracker.mark_turn_begin(self.turn))
                    try:self.turnProc(self.turn)
                    except BattlePhaseEnded as ended:state=ended.state
                    else:
                        # Only the complete skill/card phase starts a new wait
                        # budget. Animation renews stall, never phase/total hard limits.
                        progressEvent(tracker.mark_turn_input_complete(self.turn))
                if state==S.BATTLE_RESULT:
                    logger.info('Battle Finished');return True
                if state==S.DEFEATED:
                    self.defeated=True;logger.warning('Battle Defeated')
                    schedule.checkDefeated();return False
                if state==S.SPECIAL_MODAL:
                    schedule.checkKizunaReisou()
                    flow.action('close_special_battle_modal',lambda:fgoDevice.device.press('\x1B'))
                    flow.waitForFlowState({S.TURN_BEGIN,S.BATTLE_RESULT,S.DEFEATED},timeout=30,transition_name='battle modal close',allowed_intermediate={S.SPECIAL_MODAL})
                    progressEvent(tracker.progress("battle_modal_recovered"))
                elif state==S.NETWORK_ERROR:
                    flow.waitForFlowState({S.TURN_BEGIN,S.BATTLE_RESULT,S.DEFEATED},timeout=45,transition_name='battle network recovery')
                    progressEvent(tracker.progress("battle_network_recovered"))
                elif state not in {S.TURN_BEGIN,S.UNKNOWN,S.LOADING,S.BATTLE_RESULT,S.DEFEATED}:
                    flow.fail(FlowTimeout,'UNEXPECTED battle state',{S.TURN_BEGIN,S.BATTLE_RESULT,S.DEFEATED},flow.clock()-tracker.last_meaningful_progress)
                flow.trace.battle_context=tracker.snapshot()
                if tracker.stalled():
                    flow.fail(FlowTimeout,'STALL battle progress',{S.TURN_BEGIN,S.BATTLE_RESULT,S.DEFEATED},flow.clock()-tracker.last_meaningful_progress,from_state=tracker.last_positive_state)
                schedule.sleep(.2)
            flow.fail(FlowTimeout,'TIMEOUT battle total',{S.BATTLE_RESULT,S.DEFEATED},self.totalTimeout,from_state=tracker.last_positive_state)
        finally:
            flow.trace.battle_context=previousContext
            flow.deadline=previousDeadline
            INPUT_OBSERVER.reset(inputToken)
            _activeBattleFlow.reset(token)
    @property
    def result(self):
        return{
            'type':'Battle',
            'turn':self.turn,
            'time':time.time()-self.start,
            'observedDefeated':getattr(self,'defeated',False),
        }
class Main:
    teamIndex=0
    autoFormation=False
    def __init__(self,appleTotal=0,appleKind=0,battleClass=Battle,friendPolicy=None,friendMaxRefresh=2,onProgress=None):
        self.onProgress=onProgress
        self.appleTotal=appleTotal
        self.appleKind=appleKind
        self.battleClass=battleClass
        self.friendPolicy=friendPolicy
        self.friendMaxRefresh=friendMaxRefresh
        self.resetCounters()
    def makeFlow(self):
        return BattleFlow(lambda:Detect(0,0),schedule,
            trace=FlowTrace(root=paths.logRoot/'flow'),network=handleNetworkError)
    def press(self,key):
        # Menu/cycle controls only; Battle/Turn continue their original inputs.
        if XDetect.region=='CN':return fgoDevice.device.press(key,duration=.08)
        return fgoDevice.device.press(key)
    def startQuest(self):
        # CN MAXTOUCH's short tap was ignored on a verified support card;
        # 80ms down/up was observed to select it. This is one physical tap,
        # not a page-transition sleep or retry; all AI inputs stay unchanged.
        if XDetect.region=='CN':return fgoDevice.device.press(' ',duration=.08)
        return self.press(' ')
    def verifyQuest(self):
        if XDetect.region=='CN':fgoNavigation.checkCurrentQuest()
    def checkSpecialModal(self):schedule.checkKizunaReisou()
    def prepareFormation(self,flow):
        S=BattleFlowState
        if not flow.observation or flow.observation.state!=S.FORMATION:
            flow.fail(FlowTimeout,'UNVERIFIED formation',{S.FORMATION},0)
        if self.teamIndex and flow.detect.getTeamIndex()+1!=self.teamIndex:
            flow.action('select_existing_team',lambda:fgoDevice.device.press(chr(0x70+self.teamIndex-1)))
            deadline=flow.clock()+10
            while flow.clock()<deadline:
                obs=flow.observe()
                if obs.state==S.FORMATION and flow.detect.getTeamIndex()+1==self.teamIndex:break
                schedule.sleep(.2)
            else:flow.fail(FlowTimeout,'TIMEOUT team selection',{S.FORMATION},10)
        if self.autoFormation:
            flow.action('existing_auto_formation',lambda:fgoDevice.device.perform('\xDEL ',(1000,1500,1000)))
            obs=flow.observe()
            if obs.state==S.TURN_BEGIN:return
            if obs.state!=S.FORMATION:
                return flow.waitForFlowState({S.TURN_BEGIN},timeout=90,transition_name='auto formation start')
        flow.action('start_quest',self.startQuest)
        flow.trace.beginFormationStart()
        observation=flow.waitForFlowState({S.TURN_BEGIN},timeout=180,stall_timeout=60,transition_name='formation start',allowed_intermediate={S.FORMATION,S.LOADING},progress_signature=lambda d:getattr(d,'getLoadingProgressSignature',lambda:None)())
        flow.trace.endFormationStart()
        return observation
    @serialize(mutex)
    def __call__(self,questIndex=0,battleTotal=None):
        self.prepare()
        inputToken=INPUT_OBSERVER.set(self.flow.deviceInput)
        try:return self.runCycle(questIndex,battleTotal)
        finally:INPUT_OBSERVER.reset(inputToken)
    def runCycle(self,questIndex=0,battleTotal=None):
        cycle=BattleCycle(self,self.flow)
        # Every iteration has bounded preparation, battle and settlement phases.
        while battleTotal is None or self.completedAttempts<battleTotal:
            self.flow.trace.battle_sequence=self.startedBattles+1
            if not cycle.prepare(questIndex):return
            questIndex=0
            self.startedBattles+=1;self.battleCount=self.startedBattles
            self.flow.trace.battle_sequence=self.startedBattles
            logger.info(f'[BATTLE] #{self.startedBattles} confirmed TURN_BEGIN')
            self.battleProc=self.battleClass();self.battleProc.flow=self.flow
            try:won=self.battleProc()
            except ScriptStop:
                if getattr(self.battleProc,'defeated',False):
                    self.recordCompleted(False,self.battleProc.result)
                    self.emitCompleted(False,self.battleProc.result)
                raise
            battleResult=self.battleProc.result
            self.recordCompleted(won,battleResult)
            if not won:
                self.emitCompleted(False,battleResult)
                raise ScriptStop('Battle Defeated; no revival input')
            try:cycle.settleBattleResult()
            finally:self.emitCompleted(won,battleResult)
            try:schedule.checkStopLater()
            except ScriptStop as error:
                if 'Stop Appointment Effected' not in str(error):raise
                self.completionReason='Done: reached appointed battle limit'
                cycle.finish();return
        self.completionReason='Done: reached battle limit'
        cycle.finish()
    def recordCompleted(self,won,battleResult):
        self.completedAttempts+=1
        if won:
            self.wins+=1;self.battleTurn+=battleResult['turn'];self.battleTime+=battleResult['time']
        else:self.defeats+=1
        self.defeated=self.defeats
        assert self.wins+self.defeats==self.completedAttempts<=self.startedBattles
    def emitCompleted(self,won,battleResult):
        event=BattleCompleted(self.completedAttempts,self.startedBattles,self.defeats,battleResult['turn'],battleResult['time'],won,deepcopy(self.result),deepcopy(battleResult))
        if self.onProgress:self.onProgress(event)
    def prepare(self):
        if XDetect.region=='CN':
            fgoApRecovery.validateResourceCN(self.appleKind)
            fgoApRecovery.ensureNotUncertain(fgoDevice.device)
        self.resetCounters();self.flow=self.makeFlow()
    def resetCounters(self):
        self.start=time.time()
        self.startedBattles=self.battleCount=self.completedAttempts=0
        self.wins=self.defeats=self.defeated=self.stoppedDefeats=0
        self.battleTurn=0;self.battleTime=0;self.completionReason=''
    @property
    def result(self):return{
            'type':'Main','time':time.time()-self.start,
            'battle':self.completedAttempts,'startedBattles':self.startedBattles,
            'completedAttempts':self.completedAttempts,'wins':self.wins,'defeats':self.defeats,
            'progressDefeats':self.defeats,'progressWins':self.wins,'defeated':self.defeats,
            'turnPerBattle':self.battleTurn/self.wins if self.wins else 0,
            'timePerBattle':self.battleTime/self.wins if self.wins else 0,
            'completionReason':self.completionReason,
        }
    @logit(logger,logging.INFO)
    def eatApple(self,flow=None):
        if XDetect.region=='CN':return fgoApRecovery.restoreApCN(self,flow or self.makeFlow(),fgoDevice.device)
        if not self.appleTotal:return fgoDevice.device.press('Z')
        if self.appleKind==3:fgoDevice.device.perform('V',(600,))
        fgoDevice.device.perform('W4K48'[self.appleKind]+'L',(600,1200))
        self.appleTotal-=1
        logger.warning('Eat Apple')
        return self.appleTotal+1
    @logit(logger,logging.INFO)
    def chooseFriend(self,flow=None,*,continued=False):
        flow=flow or self.makeFlow()
        directBattle=continued and XDetect.region=='CN'
        policy=self.friendPolicy or 'prefer'  # CLI retains template-first behavior, now with a finite bound.
        maxRefresh=max(0,min(10,int(self.friendMaxRefresh)))
        hasTemplates=bool(friendImg.flush())
        if not fgoFriendPolicy.canStart(policy,hasTemplates):
            raise ScriptStop('助战严格模式已启用，但助战模板目录中没有 PNG 模板')
        refreshes=0
        nextRefreshAt=0
        continueWait=None
        deadline=time.monotonic()+180
        navGuard=fgoNavigation.NavigationGuard('friend selection',180,300)
        for _ in navGuard.steps():
            for _ in navGuard.steps():
                if time.monotonic()>deadline:raise ScriptStop('等待助战列表超时，请检查游戏界面')
                flow.observe();detect=flow.detect
                if XDetect.region=='CN' and detect.isBattleContinue():
                    if continueWait is None:
                        continueWait=time.monotonic()
                        fgoNavigation.publish('等待连续出击确认结束；尚未选择助战…')
                    if time.monotonic()-continueWait>=15:
                        raise ScriptStop('连续出击确认未消失；未选择助战，未进入下一场')
                    schedule.sleep(.2)
                    continue
                continueWait=None
                if detect.isChooseFriend():break
                if detect.isBattleFormation():return FriendSelectionResult(False,refreshes=refreshes)
                if detect.isNoFriend():
                    if refreshes>=maxRefresh:raise ScriptStop(f'助战列表为空，已达到最大刷新次数 {maxRefresh}')
                    schedule.sleep(max(0,nextRefreshAt-time.monotonic()))
                    fgoDevice.device.perform('\xBAK',(500,1000))
                    refreshes+=1
                    nextRefreshAt=time.monotonic()+10
                schedule.sleep(.2)
            else:
                raise ScriptStop('等待助战列表未达到预期状态；未选择助战，未进入下一场')
            # The refresh budget limits refreshes, not the initial list scan.
            if policy=='first' or not hasTemplates:
                self.waitFirstSupportReady(flow)
                flow.action('continue_support_start' if directBattle else 'select_first_support',self.selectFirstSupport)
                return self.finishFriendSelection(flow,None,refreshes,directBattle=directBattle)
            matched=False
            scrollGuard=fgoNavigation.NavigationGuard('friend list scan',60,100)
            for _ in scrollGuard.steps():
                if time.monotonic()>deadline:raise ScriptStop('扫描助战列表超时')
                for name,img in friendImg.orderedItems():
                    if pos:=Detect.cache.findFriend(img):
                        pos=self.waitTemplateSupportReady(flow,img,pos)
                        flow.action('continue_support_start' if directBattle else 'select_support_template',lambda:self.selectTemplateSupport(pos))
                        ClassicTurn.friendInfo=(lambda r:(lambda p:[
                            [[-1 if p[i*4+j]=='X'else int(p[i*4+j],16)for j in range(4)]for i in range(3)],
                            [-1 if p[i+12]=='X'else int(p[i+12],16)for i in range(2)],
                        ])(r.group())if r else[[[-1,-1,-1,-1],[-1,-1,-1,-1],[-1,-1,-1,-1]],[-1,-1]])(re.match('([0-9X]{3}[0-9A-FX]){3}[0-9X][0-9A-FX]$',name.replace('-','')[-14:].upper()))
                        return self.finishFriendSelection(flow,name,refreshes,directBattle=directBattle)
                if Detect.cache.isFriendListEnd():break
                scrollGuard.progress(fgoNavigation.stableCrop(Detect.cache,(13,166,1233,710)))
                fgoDevice.device.swipe((400,600),(400,200))
                Detect(.4)
            action=fgoFriendPolicy.decision(policy,matched,hasTemplates,refreshes,maxRefresh)
            if action=='first':
                self.waitFirstSupportReady(flow)
                flow.action('continue_support_start' if directBattle else 'select_first_support',self.selectFirstSupport)
                return self.finishFriendSelection(flow,None,refreshes,directBattle=directBattle)
            if action=='stop':raise ScriptStop(f'未找到符合模板的助战（已刷新 {refreshes} 次）')
            schedule.sleep(max(0,nextRefreshAt-time.monotonic()))
            fgoDevice.device.perform('\xBAK',(500,1000))
            refreshes+=1
            nextRefreshAt=time.monotonic()+10
    def waitTemplateSupportReady(self,flow,img,position):
        if XDetect.region!='CN':return position
        deadline=min(flow.clock()+15,flow.deadline if flow.deadline is not None else float('inf'))
        confirmed=0
        while flow.clock()<deadline:
            state=flow.observe().state
            if state==BattleFlowState.FRIEND:
                found=flow.detect.findFriend(img)
                stable=found is not None and max(abs(found[i]-position[i]) for i in range(2))<=3
                confirmed=confirmed+1 if stable else 0
                if confirmed>=3:return found
            elif state in {BattleFlowState.UNKNOWN,BattleFlowState.LOADING}:confirmed=0
            else:flow.fail(FlowTimeout,'UNEXPECTED template confirmation',{BattleFlowState.FRIEND},0)
            schedule.sleep(.2)
        flow.fail(FlowTimeout,'TIMEOUT stable support template',{BattleFlowState.FRIEND},15)
    def selectTemplateSupport(self,position):
        if XDetect.region=='CN':return fgoDevice.device.touch(position,duration=.08)
        return fgoDevice.device.touch(position)
    def waitFirstSupportReady(self,flow):
        if XDetect.region!='CN':return
        confirmed=0
        def ready(detect):
            nonlocal confirmed
            confirmed=confirmed+1 if detect.isFirstSupportReady() else 0
            return confirmed>=3
        flow.waitForFlowState({BattleFlowState.FRIEND},timeout=20,
            transition_name='first support body ready',accept=ready)
    def selectFirstSupport(self):
        # CN's first-row header at key 8 (845,203) can ignore selection.
        # Verified 1280x720 card body avoids the portrait/details controls.
        # The caller has confirmed FRIEND, and still waits for FORMATION.
        if XDetect.region=='CN':return fgoDevice.device.touch((650,300),duration=.08)
        return self.press('8')
    def finishFriendSelection(self,flow,template,refreshes,*,directBattle=False):
        # Verified CN CONTINUE may reuse the party and go straight to battle.
        # Only that route admits TURN_BEGIN; never press start after it.
        expected={BattleFlowState.FORMATION}|({BattleFlowState.TURN_BEGIN} if directBattle else set())
        timing={'timeout':180,'stall_timeout':60,'progress_signature':lambda d:getattr(d,'getLoadingProgressSignature',lambda:None)()} if directBattle else {'timeout':30}
        observation=flow.waitForFlowState(expected,**timing,
            transition_name='continue support exit' if directBattle else 'friend selection exit',allowed_intermediate={BattleFlowState.FRIEND,BattleFlowState.LOADING})
        return FriendSelectionResult(True,template,refreshes,observation.state)

class Operation(list,Main):
    apLookup={i:j for i,j in zip(missionQuest,missionMat[0])}
    def __init__(self,data=(),*args,wait=True,**kwargs):
        list.__init__(self,data)
        Main.__init__(self,*args,**kwargs)
        self.wait=wait
    def __call__(self):
        super().prepare()
        if not self:
            fgoNavigation.checkCurrentQuest()
            return super().__call__()
        while self:
            quest,times=self[0]
            goto(quest)
            if self.wait:schedule.sleep(max(self.apLookup.get(quest,23)*times-Detect.cache.getAp(),0)*300)
            fgoNavigation.publish('导航完成，正在进入关卡并选择助战…')
            before=self.completedAttempts
            try:super().__call__(quest[-1],self.completedAttempts+times if times else None)
            finally:
                remaining=max(0,times-(self.completedAttempts-before)) if times else 0
                if times and not remaining:del self[0]
                else:self[0]=(quest,remaining)
            if not times or remaining:return
    def prepare(self):pass
    def getAp(self):return sum(self.apLookup.get(i,23)*j for i,j in self)
