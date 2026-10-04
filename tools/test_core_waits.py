"""AST gate for waits in core automation; each allowed loop has a reason."""
import ast,unittest
from pathlib import Path
APP=Path(__file__).resolve().parents[1]/'FGO-py'
MODULES=('fgoKernel.py','fgoBattleFlow.py','fgoEventProgress.py','fgoGuiOperation.py')
# These collection loops make finite progress or deliberately implement the
# user's unlimited plan. Their phase/input waits remain separately bounded.
COLLECTION_LOOPS={('fgoKernel.py','ClassicTurn.dispatchSkill'),('fgoKernel.py','Turn.dispatchSkill'),
    ('fgoKernel.py','Main.runCycle'),('fgoKernel.py','Operation.__call__'),
    ('fgoGuiOperation.py','GuiQueueOperation._run')}
# Notification and optional farming daemons have explicit stop flags; they
# sleep every iteration. Farming.run takes the logical owner before input.
DAEMONS={('fgoKernel.py','guardian'),('fgoKernel.py','Farming.__call__')}

def loops(tree,scope=''):
    for node in ast.iter_child_nodes(tree):
        name=scope
        if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
            name=(scope+'.' if scope else '')+node.name
        if isinstance(node,ast.While):yield name,node
        yield from loops(node,name)

class CoreWaitTests(unittest.TestCase):
    def test_no_busy_spin_or_unguarded_infinite_loop(self):
        for filename in MODULES:
            for name,node in loops(ast.parse((APP/filename).read_text(encoding='utf-8'))):
                with self.subTest(file=filename,function=name,line=node.lineno):
                    self.assertFalse(all(isinstance(i,ast.Pass) for i in node.body),'busy spin')
                    condition=ast.unparse(node.test)
                    body=ast.unparse(node)
                    if (filename,name) in DAEMONS:
                        self.assertTrue('stop' in condition.lower());self.assertTrue('sleep(' in body or '.wait(' in condition)
                    elif (filename,name) in COLLECTION_LOOPS:
                        self.assertNotEqual(condition,'True')
                    else:
                        self.assertTrue('deadline' in condition.lower() or 'timeout' in condition.lower(),f'Unexplained loop: {name}: {condition}')
                        self.assertTrue('sleep(' in body or 'waitForFlowState(' in body)
    def test_no_repeat_sleep_six_or_blind_ten_result_inputs(self):
        tree=ast.parse((APP/'fgoKernel.py').read_text(encoding='utf-8'))
        main=next(i for i in tree.body if isinstance(i,ast.ClassDef) and i.name=='Main')
        for call in (i for i in ast.walk(main) if isinstance(i,ast.Call)):
            text=ast.unparse(call)
            self.assertNotIn('sleep(6)',text)
            self.assertNotIn("' ' * 10",text)
    def test_portable_includes_new_modules_and_remains_windowed(self):
        spec=(APP/'fgoBuildCN.spec').read_text(encoding='utf-8')
        for name in ('fgoBattleFlow','fgoFlowTrace','fgoAutomation'):self.assertIn(name,spec)
        self.assertIn('console=False',spec)

if __name__=='__main__':unittest.main()
