#!/usr/bin/env python3
"""Build the self-contained Lottie composition used only by the first landing page.

The supplied SVG already has separate body, raised-arm, and mouth groups. This
builder keeps those source groups intact as SVG image assets, then writes a Lottie
timeline for breathing, waving, and smiling. The Lottie artboard is deliberately
wider than the source SVG so the waving hand never reaches the Canvas boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOTTIE_ROOT = PROJECT_ROOT / "landing" / "zito-lottie"
SOURCE = LOTTIE_ROOT / "source" / "asset-11.svg"
ASSETS = LOTTIE_ROOT / "assets"
OUTPUT = LOTTIE_ROOT / "zito-lottie.json"

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

SOURCE_WIDTH = 261
COMPOSITION_WIDTH = 285
COMPOSITION_HEIGHT = 390
FRAME_RATE = 30
FRAME_COUNT = 180

# The source SVG was inspected once and these indexes map to its direct visual
# children. Keeping them here makes the derivation deterministic and reviewable.
RAISED_ARM_INDEX = 5
MOUTH_INDEX = 9

# Coordinates in the source SVG. The padded Lottie artboard shifts every source
# asset equally, so the mascot remains visually centered while its raised hand
# gets breathing room on both horizontal sides.
SOURCE_X_OFFSET = (COMPOSITION_WIDTH - SOURCE_WIDTH) / 2
SOURCE_OFFSET = [SOURCE_X_OFFSET, 0, 0]
ARM_SHOULDER = [172, 252, 0]
ARM_POSITION = [ARM_SHOULDER[0] + SOURCE_X_OFFSET, ARM_SHOULDER[1], 0]
MOUTH_CENTER = [123, 198, 0]
MOUTH_POSITION = [MOUTH_CENTER[0] + SOURCE_X_OFFSET, MOUTH_CENTER[1], 0]
RIG_CENTER = [COMPOSITION_WIDTH / 2, COMPOSITION_HEIGHT / 2, 0]


def _local_name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _find_layer_group(root: ET.Element) -> ET.Element:
    for node in root.iter():
        if _local_name(node) == "g" and node.attrib.get("id") == "Layer_1-2":
            return node
    raise RuntimeError("The expected Layer_1-2 group was not found in the source SVG.")


def _visual_children(root: ET.Element) -> tuple[ET.Element, list[ET.Element]]:
    layer_group = _find_layer_group(root)
    visual_group = next(
        (child for child in list(layer_group) if _local_name(child) == "g"), None
    )
    if visual_group is None:
        raise RuntimeError("The source SVG does not contain its expected visual group.")

    children = list(visual_group)
    if len(children) <= max(RAISED_ARM_INDEX, MOUTH_INDEX):
        raise RuntimeError("The source SVG layer order changed; refuse to build stale assets.")
    return visual_group, children


def _write_fragment(name: str, include_indexes: set[int]) -> None:
    tree = ET.parse(SOURCE)
    root = tree.getroot()
    visual_group, children = _visual_children(root)

    for index, child in enumerate(children):
        if index not in include_indexes:
            visual_group.remove(child)

    root.set("width", str(SOURCE_WIDTH))
    root.set("height", str(COMPOSITION_HEIGHT))
    root.set("viewBox", f"0 0 {SOURCE_WIDTH} {COMPOSITION_HEIGHT}")
    tree.write(ASSETS / name, encoding="utf-8", xml_declaration=True)


def _static_value(value: list[float] | float) -> dict:
    return {"a": 0, "k": value}


def _keyframes(values: list[tuple[int, list[float]]]) -> dict:
    frames: list[dict] = []
    for index, (frame, value) in enumerate(values):
        keyframe: dict = {"t": frame, "s": value}
        if index + 1 < len(values):
            keyframe["e"] = values[index + 1][1]
            keyframe["i"] = {"x": [0.42], "y": [1]}
            keyframe["o"] = {"x": [0.58], "y": [0]}
        frames.append(keyframe)
    return {"a": 1, "k": frames}


def _transform(
    *,
    anchor: list[float],
    position: list[float] | None = None,
    scale: dict | None = None,
    rotation: dict | None = None,
) -> dict:
    return {
        "o": _static_value(100),
        "r": rotation or _static_value(0),
        "p": _static_value(position or anchor),
        "a": _static_value(anchor),
        "s": scale or _static_value([100, 100, 100]),
    }


def _image_layer(*, index: int, name: str, ref_id: str, transform: dict) -> dict:
    return {
        "ddd": 0,
        "ind": index,
        "ty": 2,
        "nm": name,
        "refId": ref_id,
        "sr": 1,
        "ks": transform,
        "ao": 0,
        "ip": 0,
        "op": FRAME_COUNT,
        "st": 0,
        "bm": 0,
    }


def _build_lottie() -> dict:
    breathe_scale = _keyframes(
        [
            (0, [100, 100, 100]),
            (30, [101.35, 98.9, 100]),
            (60, [100, 100, 100]),
            (90, [101.35, 98.9, 100]),
            # Smile has a tiny body lift, overshoot, and settle on top of breathing.
            (120, [100, 100, 100]),
            (124, [101.8, 98.2, 100]),
            (132, [100.65, 99.45, 100]),
            (140, [100.2, 99.8, 100]),
            (151, [100, 100, 100]),
            (165, [101.35, 98.9, 100]),
            (179, [100, 100, 100]),
        ]
    )
    breathe_position = _keyframes(
        [
            (0, RIG_CENTER),
            (30, [RIG_CENTER[0], RIG_CENTER[1] - 2.4, 0]),
            (60, RIG_CENTER),
            (90, [RIG_CENTER[0], RIG_CENTER[1] - 2.4, 0]),
            (120, RIG_CENTER),
            (124, [RIG_CENTER[0], RIG_CENTER[1] - 2.5, 0]),
            (132, [RIG_CENTER[0], RIG_CENTER[1] - 0.9, 0]),
            (140, [RIG_CENTER[0], RIG_CENTER[1] + 0.3, 0]),
            (151, RIG_CENTER),
            (165, [RIG_CENTER[0], RIG_CENTER[1] - 2.4, 0]),
            (179, RIG_CENTER),
        ]
    )
    wave_rotation = _keyframes(
        [
            (0, [0]),
            (59, [0]),
            (63, [-1.75]),
            (69, [5.25]),
            (77, [-4.5]),
            (85, [4]),
            (93, [-3]),
            (101, [2.25]),
            (109, [0]),
            (179, [0]),
        ]
    )
    smile_scale = _keyframes(
        [
            (0, [100, 100, 100]),
            (119, [100, 100, 100]),
            (123, [102, 97, 100]),
            (129, [132, 70, 100]),
            (137, [116, 94, 100]),
            (143, [124, 78, 100]),
            (147, [106, 98, 100]),
            (151, [100, 100, 100]),
            (179, [100, 100, 100]),
        ]
    )
    smile_position = _keyframes(
        [
            (0, MOUTH_POSITION),
            (119, MOUTH_POSITION),
            (129, [MOUTH_POSITION[0], MOUTH_POSITION[1] - 1.2, 0]),
            (137, [MOUTH_POSITION[0], MOUTH_POSITION[1] + 0.45, 0]),
            (151, MOUTH_POSITION),
            (179, MOUTH_POSITION),
        ]
    )

    rig_layers = [
        _image_layer(
            index=1,
            name="Smile from source SVG",
            ref_id="zito-mouth",
            transform=_transform(
                anchor=MOUTH_CENTER,
                position=MOUTH_POSITION,
                scale=smile_scale,
            ) | {"p": smile_position},
        ),
        _image_layer(
            index=2,
            name="Raised arm from source SVG",
            ref_id="zito-arm",
            transform=_transform(
                anchor=ARM_SHOULDER,
                position=ARM_POSITION,
                rotation=wave_rotation,
            ),
        ),
        _image_layer(
            index=3,
            name="Static Zito body from source SVG",
            ref_id="zito-base",
            transform=_transform(anchor=[0, 0, 0], position=SOURCE_OFFSET),
        ),
    ]

    return {
        "v": "5.12.2",
        "fr": FRAME_RATE,
        "ip": 0,
        "op": FRAME_COUNT,
        "w": COMPOSITION_WIDTH,
        "h": COMPOSITION_HEIGHT,
        "nm": "Zito Landing Mascot",
        "ddd": 0,
        "assets": [
            {
                "id": "zito-rig",
                "w": COMPOSITION_WIDTH,
                "h": COMPOSITION_HEIGHT,
                "layers": rig_layers,
            },
            {
                "id": "zito-base",
                "w": SOURCE_WIDTH,
                "h": COMPOSITION_HEIGHT,
                "u": "assets/",
                "p": "zito-base.svg",
                "e": 0,
            },
            {
                "id": "zito-arm",
                "w": SOURCE_WIDTH,
                "h": COMPOSITION_HEIGHT,
                "u": "assets/",
                "p": "zito-arm.svg",
                "e": 0,
            },
            {
                "id": "zito-mouth",
                "w": SOURCE_WIDTH,
                "h": COMPOSITION_HEIGHT,
                "u": "assets/",
                "p": "zito-mouth.svg",
                "e": 0,
            },
        ],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty": 0,
                "nm": "Zito rig",
                "refId": "zito-rig",
                "sr": 1,
                "ks": _transform(
                    anchor=RIG_CENTER,
                    position=RIG_CENTER,
                    scale=breathe_scale,
                ) | {"p": breathe_position},
                "ao": 0,
                "w": COMPOSITION_WIDTH,
                "h": COMPOSITION_HEIGHT,
                "ip": 0,
                "op": FRAME_COUNT,
                "st": 0,
                "bm": 0,
            }
        ],
        "markers": [
            {"tm": 0, "cm": "idle", "dr": 60},
            {"tm": 60, "cm": "wave", "dr": 50},
            {"tm": 120, "cm": "smile", "dr": 31},
            {"tm": 60, "cm": "welcome", "dr": 91},
        ],
    }


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source SVG is missing: {SOURCE}")

    ASSETS.mkdir(parents=True, exist_ok=True)
    source_tree = ET.parse(SOURCE)
    _, visual_children = _visual_children(source_tree.getroot())
    all_indexes = set(range(len(visual_children)))

    _write_fragment("zito-base.svg", all_indexes - {RAISED_ARM_INDEX, MOUTH_INDEX})
    _write_fragment("zito-arm.svg", {RAISED_ARM_INDEX})
    _write_fragment("zito-mouth.svg", {MOUTH_INDEX})
    (ASSETS / "zito-arm.png").unlink(missing_ok=True)
    shutil.copyfile(SOURCE, ASSETS / "zito-fallback.svg")

    lottie = _build_lottie()
    OUTPUT.write_text(json.dumps(lottie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    json.loads(OUTPUT.read_text(encoding="utf-8"))
    print(f"Built {OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
