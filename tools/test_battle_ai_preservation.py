"""Protect the baseline card ranking and unchanged strategy decisions."""
import ast,hashlib,unittest
from pathlib import Path
BASELINE='add17a8a58f0315e91b695b25693c42431a61424'
# AST digests derived from the verified baseline (no source line numbers).
GOLDEN={'ClassicTurn.__init__': '9060748241215edf831d184cbba2900aa095735c65daccad1c344ab108b6a5ee', 'ClassicTurn.__call__': '5e9cebcee5b047137a4f5a7b7376cc1a19fb7508980b5b8564e28c15e6ffffaf', 'ClassicTurn.selectCard': '41f655efc4bc87a75262cedda4680c0d9048b9e895889a1683477cf923f90066', 'ClassicTurn.getSkillInfo': '136151ed20fbde9bc5347eb0f9709ee20861b38dc3ee0575eb54bdaeeabcd76e', 'ClassicTurn.getHouguInfo': '479922217b76f47c2376ccac9311d96a25d1d3e2c4f871df6674d2c5ed14fd56', 'Turn.__init__': 'b455e163a0e71407908de32c05448f41d09f3d67e67f0ff25871c042029981bd', 'Turn.__call__': 'b7e7f7c6ec315b5b6c686445a8533a6201b25a9c3784e1a9c8d094de77e8719a', 'Turn.dispatchSkill': 'bfb3fa82424755c8261d53663c6539faa38572770c7477a57afaee4e1cb9af79', 'Turn.selectCard': '4c02f7c5cb69a1d00cd482f18925a14930bbbc3253314adb48a110ee3333c8c2'}
class AiPreservationTests(unittest.TestCase):
    def test_baseline_card_and_strategy_ast_unchanged(self):
        source=Path(__file__).resolve().parents[1]/'FGO-py/fgoKernel.py'
        tree=ast.parse(source.read_text(encoding='utf-8'))
        methods={c.name+'.'+f.name:f for c in tree.body if isinstance(c,ast.ClassDef) for f in c.body if isinstance(f,ast.FunctionDef)}
        for name,digest in GOLDEN.items():
            with self.subTest(method=name):
                self.assertEqual(hashlib.sha256(ast.dump(methods[name]).encode()).hexdigest(),digest)
if __name__=='__main__':unittest.main()
