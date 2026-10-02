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
import fgoDevice
import fgoDrop
import fgoFriendPolicy
import fgoNavigation
from itertools import permutations
from functools import wraps
from fgoDetect import Detect,XDetect,OCR
from fgoFuse import fuse
from fgoImageListener import ImageListener
from fgoFriendTemplates import FriendTemplateStore
from fgoProgress import BattleCompleted
from fgoLogging import getLogger,logit
from fgoMetadata import servantData,missionMat,missionTag,missionQuest
from fgoReishift import reishift
from fgoSchedule import ScriptStop,schedule
logger=getLogger('Kernel')

friendImg=FriendTemplateStore('fgoImage/friend/')
mailImg=ImageListener('fgoImage/mail/')
mutex=threading.Lock()
def serialize(lock):
    def decorator(func):
        @wraps(func)
        def wrapper(*args,**kwargs):
            with lock:return func(*args,**kwargs)
        return wrapper
    return decorator
def guardian():
    logger=logging.getLogger('Guardian')
    prev=None
    while True:
        while XDetect.cache is prev:time.sleep(3)
        if XDetect.cache.isNetworkError():
            logger.warning('Reconnecting')
            fgoDevice.device.press('K')
        prev=XDetect.cache
threading.Thread(target=guardian,daemon=True,name='Guardian').start()
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
            while not Detect().isTurnBegin():pass
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
            fgoDevice.device.press('J')
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
                while not Detect().isTurnBegin():pass
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
            fgoDevice.device.press('J')
        elif t:=Detect.cache.getSkillTargetCount():fgoDevice.device.perform(['3333','2244','3234'][t-1][f-5 if(f:=self.servant[pos][6][skill][1])in{6,7,8}else target]+'\x08',(300,700))
        else:fgoDevice.device.perform('\x08',(700,))
        while not Detect().isTurnBegin():pass
        Detect(.5)
    def castMasterSkill(self,skill,target):
        self.countDown[1][skill]=15
        fgoDevice.device.perform('Q'+'WER'[skill],(300,300))
        if t:=Detect(.4).getSkillTargetCount():fgoDevice.device.perform(['3333','2244','3234'][t-1][target],(300,))
        while not Detect().isTurnBegin():pass
        Detect(.5)
class Battle:
    def __init__(self,turnClass=Turn):
        self.turn=0
        self.turnProc=turnClass()
        self.rainbowBox=False
    def __call__(self):
        self.start=time.time()
        self.material={}
        self.dropStats={}
        self.unknownDrops=[]
        self.defeated=False
        while True:
            if Detect(0,.3).isTurnBegin():
                self.turn+=1
                self.turnProc(self.turn)
            elif Detect.cache.isSpecialDropSuspended():
                schedule.checkKizunaReisou()
                logger.warning('Kizuna Reisou')
                Detect.cache.save('fgoLog/SpecialDrop')
                fgoDevice.device.press('\x1B')
            elif not self.rainbowBox and Detect.cache.isSpecialDropRainbowBox():self.rainbowBox=True
            elif Detect.cache.isBattleFinished():
                logger.info('Battle Finished')
                frame=Detect(.4)
                try:
                    drops=frame.getDropResult()
                    self.material=drops.recognized;self.dropStats=drops.stats;self.unknownDrops=drops.unknown_crops
                except Exception as e:
                    logger.exception('Drop detection failed; continuing result processing')
                    self.dropStats={'errors':[str(e)],'unknown_slots':0,'occupied_slots':0,'recognized_slots':0,'incomplete':True}
                    self.unknownDrops=[{'reason':'entire result could not be analyzed'}]
                if self.rainbowBox:
                    logger.warning('Special Drop')
                    schedule.checkSpecialDrop()
                    Detect.cache.save('fgoLog/SpecialDrop')
                return True
            elif Detect.cache.isBattleDefeated():
                self.defeated=True
                logger.warning('Battle Defeated')
                schedule.checkDefeated()
                return False
            fgoDevice.device.perform('\xBB\x08',(100,100))
    @property
    def result(self):
        return{
            'type':'Battle',
            'turn':self.turn,
            'time':time.time()-self.start,
            'material':self.material,
            'dropStats':getattr(self,'dropStats',{}),
            'unknownDrops':getattr(self,'unknownDrops',[]),
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
    @serialize(mutex)
    def __call__(self,questIndex=0,battleTotal=None):
        self.prepare()
        while True:
            self.battleProc=self.battleClass()
            navGuard=fgoNavigation.NavigationGuard('battle preparation',180,300)
            for _ in navGuard.steps():
                if Detect(.3,.3).isMainInterface():
                    if self.battleCount==battleTotal:return logger.info('Operation Unit Completed')
                    if XDetect.region=='CN':fgoNavigation.checkCurrentQuest()
                    fgoDevice.device.press('84L'[questIndex])
                    questIndex=0
                    if Detect(1.2).isBattleContinue():fgoDevice.device.press('K')
                    elif Detect.cache.isSkillCastFailed():
                        fgoDevice.device.press('J')
                        return logger.info('No Storm Pot')
                    if Detect(.7,.3).isApEmpty()and not self.eatApple():return logger.info('Ap Empty')
                    self.chooseFriend()
                    navGuard.wait(lambda d:d.isBattleFormation(),'battle formation')
                    if self.teamIndex and Detect.cache.getTeamIndex()+1!=self.teamIndex:fgoDevice.device.perform('\x70\x71\x72\x73\x74\x75\x76\x77\x78\x79\x7A\x7B\x7C\x7D\x7E'[self.teamIndex-1],(1000,))
                    if self.autoFormation:fgoDevice.device.perform('\xDEL ',(1000,1500,1000))
                    fgoDevice.device.perform(' M ',(2000,2000,10000))
                    break
                elif Detect.cache.isBattleContinue():
                    if self.battleCount==battleTotal:
                        fgoDevice.device.press('F')
                        return logger.info('Operation Unit Completed')
                    fgoDevice.device.press('K')
                    if Detect(.7,.3).isApEmpty()and not self.eatApple():return logger.info('Ap Empty')
                    self.chooseFriend()
                    schedule.sleep(6)
                    break
                elif Detect.cache.isSkillCastFailed():
                    fgoDevice.device.press('J')
                    return logger.info('No Storm Pot')
                elif Detect.cache.isTurnBegin():break
                elif Detect.cache.isAddFriend():fgoDevice.device.perform('X',(300,))
                elif Detect.cache.isSpecialDropSuspended():fgoDevice.device.perform('\x1B',(300,))
                fgoDevice.device.press('\xBB')
            self.battleCount+=1
            logger.info(f'Battle {self.battleCount}')
            try:won=self.battleProc()
            except ScriptStop:
                # Preserve the upstream immediate stop on defeat: no revive or
                # result inputs. Record the confirmed outcome for display only.
                if getattr(self.battleProc,'defeated',False):
                    self.stoppedDefeats+=1
                    self.completedAttempts+=1
                    self.emitCompleted(False,self.battleProc.result)
                raise
            if won:
                battleResult=self.battleProc.result
                self.battleTurn+=battleResult['turn']
                self.battleTime+=battleResult['time']
                self.material={i:self.material.get(i,0)+battleResult['material'].get(i,0)for i in self.material|battleResult['material']}
                fgoDrop.mergeStats(self.dropStats,battleResult.get('dropStats',{}))
                self.unknownDrops.extend(battleResult.get('unknownDrops',[]))
                fgoDevice.device.perform(' '*10,(400,)*10)
            else:
                battleResult=self.battleProc.result
                self.defeated+=1
                fgoDevice.device.perform('CIK',(500,500,500))
            self.completedAttempts+=1
            self.emitCompleted(won,battleResult)
            schedule.checkStopLater()
    def emitCompleted(self,won,battleResult):
        event=BattleCompleted(self.completedAttempts,self.battleCount,self.defeated+self.stoppedDefeats,battleResult['turn'],battleResult['time'],won,deepcopy(self.result),deepcopy(battleResult))
        if self.onProgress:self.onProgress(event)
    def prepare(self):
        self.start=time.time()
        self.material={}
        self.dropStats={}
        self.unknownDrops=[]
        self.battleCount=0
        self.completedAttempts=0
        self.stoppedDefeats=0
        self.battleTurn=0
        self.battleTime=0
        self.defeated=0
    @property
    def result(self):return{
            'type':'Main',
            'time':time.time()-self.start,
            'battle':self.battleCount,
            'completedAttempts':self.completedAttempts,
            'progressDefeats':self.defeated+self.stoppedDefeats,
            'progressWins':self.completedAttempts-self.defeated-self.stoppedDefeats,
            'defeated':self.defeated,
            'turnPerBattle':self.battleTurn/(self.battleCount-self.defeated)if self.battleCount-self.defeated else 0,
            'timePerBattle':self.battleTime/(self.battleCount-self.defeated)if self.battleCount-self.defeated else 0,
            'material':self.material,
            'dropStats':getattr(self,'dropStats',{}),
            'unknownDrops':getattr(self,'unknownDrops',[]),
        }
    @logit(logger,logging.INFO)
    def eatApple(self):
        if not self.appleTotal:return fgoDevice.device.press('Z')
        if self.appleKind==3:fgoDevice.device.perform('V',(600,))
        fgoDevice.device.perform('W4K48'[self.appleKind]+'L',(600,1200))
        self.appleTotal-=1
        logger.warning('Eat Apple')
        return self.appleTotal+1
    @logit(logger,logging.INFO)
    def chooseFriend(self):
        policy=self.friendPolicy or 'prefer'  # CLI retains template-first behavior, now with a finite bound.
        maxRefresh=max(0,min(10,int(self.friendMaxRefresh)))
        hasTemplates=bool(friendImg.flush())
        if not fgoFriendPolicy.canStart(policy,hasTemplates):
            raise ScriptStop('助战严格模式已启用，但助战模板目录中没有 PNG 模板')
        refreshes=0
        nextRefreshAt=0
        deadline=time.time()+180
        navGuard=fgoNavigation.NavigationGuard('friend selection',180,300)
        for _ in navGuard.steps():
            for _ in navGuard.steps():
                if time.time()>deadline:raise ScriptStop('等待助战列表超时，请检查游戏界面')
                detect=Detect(0,.3)
                if detect.isChooseFriend():break
                if detect.isBattleFormation():return
                if detect.isNoFriend():
                    if refreshes>=maxRefresh:raise ScriptStop(f'助战列表为空，已达到最大刷新次数 {maxRefresh}')
                    schedule.sleep(max(0,nextRefreshAt-time.time()))
                    fgoDevice.device.perform('\xBAK',(500,1000))
                    refreshes+=1
                    nextRefreshAt=time.time()+10
            # The refresh budget limits refreshes, not the initial list scan.
            if policy=='first' or not hasTemplates:return fgoDevice.device.press('8')
            matched=False
            scrollGuard=fgoNavigation.NavigationGuard('friend list scan',60,100)
            for _ in scrollGuard.steps():
                if time.time()>deadline:raise ScriptStop('扫描助战列表超时')
                for name,img in friendImg.orderedItems():
                    if pos:=Detect.cache.findFriend(img):
                        fgoDevice.device.touch(pos)
                        ClassicTurn.friendInfo=(lambda r:(lambda p:[
                            [[-1 if p[i*4+j]=='X'else int(p[i*4+j],16)for j in range(4)]for i in range(3)],
                            [-1 if p[i+12]=='X'else int(p[i+12],16)for i in range(2)],
                        ])(r.group())if r else[[[-1,-1,-1,-1],[-1,-1,-1,-1],[-1,-1,-1,-1]],[-1,-1]])(re.match('([0-9X]{3}[0-9A-FX]){3}[0-9X][0-9A-FX]$',name.replace('-','')[-14:].upper()))
                        return name
                if Detect.cache.isFriendListEnd():break
                scrollGuard.progress(fgoNavigation.stableCrop(Detect.cache,(13,166,1233,710)))
                fgoDevice.device.swipe((400,600),(400,200))
                Detect(.4)
            action=fgoFriendPolicy.decision(policy,matched,hasTemplates,refreshes,maxRefresh)
            if action=='first':return fgoDevice.device.press('8')
            if action=='stop':raise ScriptStop(f'未找到符合模板的助战（已刷新 {refreshes} 次）')
            schedule.sleep(max(0,nextRefreshAt-time.time()))
            fgoDevice.device.perform('\xBAK',(500,1000))
            refreshes+=1
            nextRefreshAt=time.time()+10
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
            before=self.battleCount
            try:super().__call__(quest[-1],self.battleCount+times if times else None)
            finally:
                remaining=max(0,times-(self.battleCount-before)) if times else 0
                if times and not remaining:del self[0]
                else:self[0]=(quest,remaining)
            if not times or remaining:return
    def prepare(self):pass
    def getAp(self):return sum(self.apLookup.get(i,23)*j for i,j in self)
