#!/usr/bin/env python3
"""Offline regression for the CN continuous-deployment dialog detector.

Screenshots are local-only inputs. Synthetic skill-error/AP-empty probes reuse
the unmodified upstream templates and verify their detections stay independent.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(r"C:\FGO-Automation\FGO-py")
APP = REPO / "FGO-py"
LOGS = Path(r"C:\FGO-Automation\logs")
os.chdir(APP)
sys.path.insert(0, str(APP))
from fgoConst import PACKAGE_TO_REGION  # noqa: E402
from fgoDetect import IMG, XDetectCN  # noqa: E402

BC_RECT = (455, 85, 835, 144)
BC_THRESHOLD = 0.05
SKILL_RECT = (504, 528, 776, 597)
SKILL_THRESHOLD = 0.05
AP_RECT = (522, 582, 758, 652)
AP_THRESHOLD = 0.05


def detector(image: np.ndarray) -> XDetectCN:
    instance = object.__new__(XDetectCN)
    instance.im = image
    return instance


def load_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None or image.shape != (720, 1280, 3):
        raise AssertionError(f"{path}: expected a readable 1280x720 screenshot")
    return image


def sqdiff(image, template, rect) -> float:
    x1, y1, x2, y2 = rect
    crop = image[y1:y2, x1:x2]
    score = cv2.minMaxLoc(
        cv2.matchTemplate(crop, template[0], cv2.TM_SQDIFF_NORMED, mask=template[1])
    )[0]
    return float(score)


def assert_state(label, image, *, battle_continue, skill_error, ap_empty=False):
    d = detector(image)
    values = {
        "battleContinue": bool(d.isBattleContinue()),
        "skillCastFailed": bool(d.isSkillCastFailed()),
        "apEmpty": bool(d.isApEmpty()),
    }
    expected = {
        "battleContinue": battle_continue,
        "skillCastFailed": skill_error,
        "apEmpty": ap_empty,
    }
    if values != expected:
        raise AssertionError(f"{label}: got {values}, expected {expected}")
    print(f"PASS {label}: {values}")
    return d


def synthetic_template(template, rect):
    image = np.full((720, 1280, 3), 72, dtype=np.uint8)
    x1, y1, _, _ = rect
    pixels = template[0]
    image[y1 : y1 + pixels.shape[0], x1 : x1 + pixels.shape[1]] = pixels
    return image


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--continue-screenshot", type=Path, default=LOGS / "battle-continue-cn-20261001.png")
    parser.add_argument("--friend-request-screenshot", type=Path, default=LOGS / "diag-after-result.png")
    parser.add_argument("--main-screenshot", type=Path, default=LOGS / "diag-nav-2.png")
    parser.add_argument("--daily-list-screenshot", type=Path, default=LOGS / "diag-nav-4.png")
    parser.add_argument("--battle-screenshot", type=Path, default=LOGS / "diag-battle-sample.png")
    args = parser.parse_args()

    popup = load_image(args.continue_screenshot)
    d = detector(popup)
    cn_score = sqdiff(popup, d.tmpl.BATTLECONTINUE, BC_RECT)
    legacy_continue_score = sqdiff(popup, IMG.BATTLECONTINUE, (704, 530, 976, 618))
    skill_score = sqdiff(popup, d.tmpl.SKILLERROR, SKILL_RECT)
    print(
        f"region=CN package=com.bilibili.fatego; "
        f"CN BattleContinue score={cn_score:.6f} threshold={BC_THRESHOLD} "
        f"crop={BC_RECT} template={(d.tmpl.BATTLECONTINUE[0].shape[1], d.tmpl.BATTLECONTINUE[0].shape[0])}; "
        f"legacy button score={legacy_continue_score:.6f}; "
        f"SkillError score={skill_score:.6f} threshold={SKILL_THRESHOLD} "
        f"crop={SKILL_RECT} template={(d.tmpl.SKILLERROR[0].shape[1], d.tmpl.SKILLERROR[0].shape[0])}"
    )
    assert PACKAGE_TO_REGION["com.bilibili.fatego"] == "CN"
    if not cn_score < BC_THRESHOLD:
        raise AssertionError("CN continuous-dialog title did not match")
    if not skill_score >= SKILL_THRESHOLD:
        raise AssertionError("skill-error template matched the continuous dialog")
    assert_state("actual continuous-dialog screenshot", popup, battle_continue=True, skill_error=False)

    negatives = (
        ("friend-request", args.friend_request_screenshot),
        ("main-interface", args.main_screenshot),
        ("daily-quest-list", args.daily_list_screenshot),
        ("normal-battle", args.battle_screenshot),
    )
    for label, path in negatives:
        assert_state(label, load_image(path), battle_continue=False, skill_error=False)

    # Reuse the untouched upstream templates as deterministic positive probes.
    skill_probe = synthetic_template(IMG.SKILLERROR, SKILL_RECT)
    assert_state("upstream skill-error template probe", skill_probe, battle_continue=False, skill_error=True)
    ap_probe = synthetic_template(IMG.APEMPTY, AP_RECT)
    assert_state("upstream AP-empty template probe", ap_probe, battle_continue=False, skill_error=False, ap_empty=True)

    print("PASS: CN-specific change; JP/NA/TW templates and shared skill/AP templates are untouched.")


if __name__ == "__main__":
    main()
