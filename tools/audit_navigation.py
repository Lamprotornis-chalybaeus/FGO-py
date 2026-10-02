"""Static inventory of every while loop, with no imports of the game runtime."""
import ast,argparse,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE='049714f54a1888337c5e6a9ffd0c56b3167ef2f7'
MENU={
 'fgoReishift.py':None,
 'fgoKernel.py':{'setup','fpSummon','lottery','mail','synthesis','dailyFpSummon','dailyStorySummon','summonHistory','goto','_weeklyMissionDetailed','Main.chooseFriend'},
 'fgoQuickQuest.py':None,
 'fgoEventProgress.py':None,
 'fgoNavigation.py':None,
}
def loops(filename,source):
    result=[]
    def visit(node,scope=()):
        if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):scope=(*scope,node.name)
        if isinstance(node,ast.While):
            owner='.'.join(scope);condition=ast.unparse(node.test)
            preparation=filename=='fgoKernel.py' and owner=='Main.__call__' and node.body and isinstance(node.body[0],ast.If)
            menu=preparation or (filename in MENU and (MENU[filename] is None or owner in MENU[filename]))
            if menu:
                protection='explicit deadline' if 'deadline' in condition else 'legacy visual loop: inspect/fix'
                category='menu/navigation'
            elif filename in ('fgoGuiOperation.py','fgoKernel.py') and owner in ('GuiQueueOperation.__call__','Operation.__call__'):
                category='queue execution';protection='each goto has deadline; battle repetitions intentionally user controlled'
            elif filename=='fgoKernel.py' and owner in ('guardian','Farming.__call__'):
                category='background watcher';protection='not a navigation loop; daemon lifetime / stop flag'
            elif filename=='fgoKernel.py':
                category='battle';protection='battle animation/turn/action loop: outside this menu-only change'
            elif filename=='fgoDetect.py':
                category='recognition generator/helper';protection='yield suspends coroutine / decreasing finite collection'
            elif filename=='fgoSchedule.py':
                category='scheduler';protection='stop check / clock deadline'
            elif filename=='fgoAndroid.py':
                category='gesture transport';protection='finite geometric distance; not menu state navigation'
            else:category='runtime/helper';protection='inspect purpose; not a menu route'
            result.append({'file':filename,'function':owner,'line':node.lineno,'condition':condition,'category':category,'protection':protection})
        for child in ast.iter_child_nodes(node):visit(child,scope)
    visit(ast.parse(source));return result
def inventory(baseline=False):
    out=[]
    for path in sorted((ROOT/'FGO-py').glob('*.py')):
        if baseline:
            proc=subprocess.run(['git','show',f'{BASE}:FGO-py/{path.name}'],cwd=ROOT,capture_output=True)
            if proc.returncode:
                if path.name=='fgoNavigation.py':continue
                raise RuntimeError(f'Cannot read baseline {path.name}: {proc.stderr.decode(errors="replace")}')
            source=proc.stdout.decode('utf-8-sig')
        else:source=path.read_text(encoding='utf-8-sig')
        out.extend(loops(path.name,source))
    return out
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=pathlib.Path,required=True);args=parser.parse_args()
    before=inventory(True);after=inventory()
    data={'baseline':BASE,'before':before,'after':after}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.with_suffix('.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# Navigation while-loop audit','',f'Baseline: `{BASE}`','', 'Every executable while loop in top-level FGO-py Python modules is inventoried below. Commented-out code is excluded.','', '## Before','', '| File | Function | Line | Condition | Purpose | Protection |','| --- | --- | --- | --- | --- | --- |']
    for row in before:lines.append('| '+' | '.join(str(row[key]).replace('|','/').replace('\n',' ') for key in ('file','function','line','condition','category','protection'))+' |')
    lines+=['','## After','','| File | Function | Line | Condition | Purpose | Protection |','| --- | --- | --- | --- | --- | --- |']
    for row in after:lines.append('| '+' | '.join(str(row[key]).replace('|','/').replace('\n',' ') for key in ('file','function','line','condition','category','protection'))+' |')
    lines+=['','## Finite navigation loops replacing legacy while loops','',
      '- fgoReishift.List / Map: NavigationGuard, finite steps, deadlines, no-progress checks. CN chapter lists bypass old hierarchy; CN special maps reject unverified routes.',
      '- fgoKernel.goto: overall 180-second budget; CN explicit page routing and target verification. Legacy Free Quest scans bounded.',
      '- fgoKernel._weeklyMissionDetailed: 240-second budget, panel wait bound, real scrollbar boundaries, task-count verification, list no-progress detection.',
      '- Main preparation: finite 180-second state guard, formation wait bound; CN list preflight before quest selection.',
      '- Main.chooseFriend: 180-second overall bound, refresh count, 60-second per-scroll bound, no-progress detection.',
      '- Mail / synthesis / summon / history / lottery: legacy waits and loops bounded; unverified CN mutation/navigation paths stop before input. None executed.',
      '- Event navigation: existing finite loops plus 90-second entry deadline; no event combat or mission solving tested.',
      '- Daily routing: original implementation unchanged; full scan / return / locate use their existing deadlines and real scrollbar bounds.',
      '', '## Retained non-navigation loops and limits','',
      '- Battle skill/turn/animation loops retain upstream behavior; this request excludes combat testing. Fuse/schedule stop checks remain, but not all battle waits have a dedicated wall-clock deadline.',
      '- Guardian/Farming and image-directory watchers are long-lived daemon services. Coroutine yield loops suspend for their caller; interactive CLI generators are intentional.',
      '- Android swipe is a finite-distance transport loop. Schedule pause is user-controlled and checks stop; scheduled sleep uses a clock deadline.',
      '- Detect.retryOnError is recursive rather than a while loop and can retry indefinitely. Navigation here uses non-recursive state/OCR primitives; broader recognition retry changes are deferred.',
      '- Native screenshot/ADB/OCR calls are synchronous. Guards bound transitions between calls; a hung external call is not forcibly killed by NavigationGuard.',
      '- Legacy non-CN fixed multi-tap special-map sequences are finite and have bounded entry waits, but have not been visually validated on this CN device.',
      '']
    args.output.write_text('\n'.join(lines),encoding='utf-8')
    print(f'before={len(before)} while loops, after={len(after)}; report={args.output}')
if __name__=='__main__':main()
