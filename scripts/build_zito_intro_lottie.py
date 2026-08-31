#!/usr/bin/env python3
"""Build the Canvas Lottie composition for Zito's introduction landing page.

The source SVG keeps Zito's two eyes and smile as independent paths inside the
face group. This builder preserves the supplied avatar exactly, then derives
three Lottie image assets: static body, eyes, and smile. Only breathing, a
gentle upward eye glance, and a small smile motion are animated.
"""

from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOTTIE_ROOT = PROJECT_ROOT / "landing" / "zito-intro-lottie"
SOURCE = LOTTIE_ROOT / "source" / "zito-intro.svg"
ASSETS = LOTTIE_ROOT / "assets"
OUTPUT = LOTTIE_ROOT / "zito-intro-lottie.json"

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

SOURCE_WIDTH = 2052
SOURCE_HEIGHT = 3918
PADDING_X = 110
PADDING_Y = 100
COMPOSITION_WIDTH = SOURCE_WIDTH + (PADDING_X * 2)
COMPOSITION_HEIGHT = SOURCE_HEIGHT + (PADDING_Y * 2)
FRAME_RATE = 30
FRAME_COUNT = 180

# These are source-SVG indexes, intentionally kept together so source changes
# fail fast instead of silently animating the wrong part of the mascot.
FACE_GROUP_INDEX = 9
MOUTH_FEATURE_INDEX = 2
EYE_FEATURE_INDEXES = {3, 4}
FACE_FEATURE_INDEXES = EYE_FEATURE_INDEXES | {MOUTH_FEATURE_INDEX}

SOURCE_OFFSET = [PADDING_X, PADDING_Y, 0]
EYES_CENTER = [1028, 1742, 0]
EYES_POSITION = [EYES_CENTER[0] + PADDING_X, EYES_CENTER[1] + PADDING_Y, 0]
MOUTH_CENTER = [1043, 1980, 0]
MOUTH_POSITION = [MOUTH_CENTER[0] + PADDING_X, MOUTH_CENTER[1] + PADDING_Y, 0]
RIG_CENTER = [COMPOSITION_WIDTH / 2, COMPOSITION_HEIGHT / 2, 0]


def _local_name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _visual_children(root: ET.Element) -> tuple[ET.Element, list[ET.Element]]:
    layer_group = next(
        (node for node in root.iter() if _local_name(node) == "g" and node.attrib.get("id") == "Layer_1-2"),
        None,
    )
    if layer_group is None:
        raise RuntimeError("The expected Layer_1-2 group was not found in the intro source SVG.")

    visual_group = next((child for child in list(layer_group) if _local_name(child) == "g"), None)
    if visual_group is None:
        raise RuntimeError("The intro source SVG does not contain its expected visual group.")

    children = list(visual_group)
    if len(children) <= FACE_GROUP_INDEX:
        raise RuntimeError("The intro source SVG layer order changed; refuse to build stale assets.")
    face_children = list(children[FACE_GROUP_INDEX])
    if len(face_children) <= max(FACE_FEATURE_INDEXES):
        raise RuntimeError("The intro face paths changed; refuse to build stale animation assets.")
    return visual_group, children


def _write_fragment(
    name: str,
    include_outer_indexes: set[int],
    *,
    face_feature_indexes: set[int] | None = None,
    feature_only: bool = False,
) -> None:
    tree = ET.parse(SOURCE)
    root = tree.getroot()
    visual_group, outer_children = _visual_children(root)
    face_group = outer_children[FACE_GROUP_INDEX]

    for index, child in enumerate(outer_children):
        if index not in include_outer_indexes:
            visual_group.remove(child)

    if FACE_GROUP_INDEX in include_outer_indexes and face_feature_indexes is not None:
        for index, child in enumerate(list(face_group)):
            if feature_only:
                if index not in face_feature_indexes:
                    face_group.remove(child)
            elif index in FACE_FEATURE_INDEXES and index not in face_feature_indexes:
                face_group.remove(child)

    root.set("width", str(SOURCE_WIDTH))
    root.set("height", str(SOURCE_HEIGHT))
    root.set("viewBox", f"0 0 {SOURCE_WIDTH} {SOURCE_HEIGHT}")
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
) -> dict:
    return {
        "o": _static_value(100),
        "r": _static_value(0),
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
            (38, [100.85, 99.28, 100]),
            (76, [100, 100, 100]),
            (114, [100.85, 99.28, 100]),
            (152, [100, 100, 100]),
            (179, [100.58, 99.52, 100]),
        ]
    )
    breathe_position = _keyframes(
        [
            (0, RIG_CENTER),
            (38, [RIG_CENTER[0], RIG_CENTER[1] - 15, 0]),
            (76, RIG_CENTER),
            (114, [RIG_CENTER[0], RIG_CENTER[1] - 15, 0]),
            (152, RIG_CENTER),
            (179, [RIG_CENTER[0], RIG_CENTER[1] - 8, 0]),
        ]
    )
    eyes_position = _keyframes(
        [
            (0, EYES_POSITION),
            (31, EYES_POSITION),
            (40, [EYES_POSITION[0], EYES_POSITION[1] - 11, 0]),
            (48, [EYES_POSITION[0], EYES_POSITION[1] - 29, 0]),
            (57, [EYES_POSITION[0], EYES_POSITION[1] - 12, 0]),
            (67, EYES_POSITION),
            (104, EYES_POSITION),
            (113, [EYES_POSITION[0], EYES_POSITION[1] - 10, 0]),
            (121, [EYES_POSITION[0], EYES_POSITION[1] - 24, 0]),
            (130, [EYES_POSITION[0], EYES_POSITION[1] - 8, 0]),
            (140, EYES_POSITION),
            (179, EYES_POSITION),
        ]
    )
    eyes_scale = _keyframes(
        [
            (0, [100, 100, 100]),
            (31, [100, 100, 100]),
            (48, [101.2, 94.5, 100]),
            (57, [100.4, 98.4, 100]),
            (67, [100, 100, 100]),
            (104, [100, 100, 100]),
            (121, [100.9, 95.8, 100]),
            (130, [100.3, 98.7, 100]),
            (140, [100, 100, 100]),
            (179, [100, 100, 100]),
        ]
    )
    smile_position = _keyframes(
        [
            (0, MOUTH_POSITION),
            (51, MOUTH_POSITION),
            (61, [MOUTH_POSITION[0], MOUTH_POSITION[1] - 6, 0]),
            (70, [MOUTH_POSITION[0], MOUTH_POSITION[1] + 3, 0]),
            (80, MOUTH_POSITION),
            (137, MOUTH_POSITION),
            (147, [MOUTH_POSITION[0], MOUTH_POSITION[1] - 5, 0]),
            (156, [MOUTH_POSITION[0], MOUTH_POSITION[1] + 2, 0]),
            (166, MOUTH_POSITION),
            (179, MOUTH_POSITION),
        ]
    )
    smile_scale = _keyframes(
        [
            (0, [100, 100, 100]),
            (51, [100, 100, 100]),
            (61, [106, 96, 100]),
            (70, [118, 80, 100]),
            (76, [108, 94, 100]),
            (80, [100, 100, 100]),
            (137, [100, 100, 100]),
            (147, [104, 97, 100]),
            (156, [113, 86, 100]),
            (162, [105, 96, 100]),
            (166, [100, 100, 100]),
            (179, [100, 100, 100]),
        ]
    )

    rig_layers = [
        _image_layer(
            index=1,
            name="Eyes from source SVG looking upward",
            ref_id="zito-intro-eyes",
            transform=_transform(
                anchor=EYES_CENTER,
                position=EYES_POSITION,
                scale=eyes_scale,
            ) | {"p": eyes_position},
        ),
        _image_layer(
            index=2,
            name="Smile from source SVG",
            ref_id="zito-intro-mouth",
            transform=_transform(
                anchor=MOUTH_CENTER,
                position=MOUTH_POSITION,
                scale=smile_scale,
            ) | {"p": smile_position},
        ),
        _image_layer(
            index=3,
            name="Static Zito introduction body from source SVG",
            ref_id="zito-intro-base",
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
        "nm": "Zito Introduction Mascot",
        "ddd": 0,
        "assets": [
            {
                "id": "zito-intro-rig",
                "w": COMPOSITION_WIDTH,
                "h": COMPOSITION_HEIGHT,
                "layers": rig_layers,
            },
            {
                "id": "zito-intro-base",
                "w": SOURCE_WIDTH,
                "h": SOURCE_HEIGHT,
                "u": "assets/",
                "p": "zito-intro-base.svg",
                "e": 0,
            },
            {
                "id": "zito-intro-eyes",
                "w": SOURCE_WIDTH,
                "h": SOURCE_HEIGHT,
                "u": "assets/",
                "p": "zito-intro-eyes.svg",
                "e": 0,
            },
            {
                "id": "zito-intro-mouth",
                "w": SOURCE_WIDTH,
                "h": SOURCE_HEIGHT,
                "u": "assets/",
                "p": "zito-intro-mouth.svg",
                "e": 0,
            },
        ],
        "layers": [
            {
                "ddd": 0,
                "ind": 1,
                "ty": 0,
                "nm": "Zito introduction rig",
                "refId": "zito-intro-rig",
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
            {"tm": 0, "cm": "idle", "dr": 180},
            {"tm": 31, "cm": "eyes-look-up", "dr": 37},
            {"tm": 51, "cm": "smile", "dr": 30},
        ],
    }


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Source SVG is missing: {SOURCE}")

    ASSETS.mkdir(parents=True, exist_ok=True)
    source_tree = ET.parse(SOURCE)
    _, visual_children = _visual_children(source_tree.getroot())
    all_indexes = set(range(len(visual_children)))

    _write_fragment(
        "zito-intro-base.svg",
        all_indexes,
        face_feature_indexes=set(),
    )
    _write_fragment(
        "zito-intro-eyes.svg",
        {FACE_GROUP_INDEX},
        face_feature_indexes=EYE_FEATURE_INDEXES,
        feature_only=True,
    )
    _write_fragment(
        "zito-intro-mouth.svg",
        {FACE_GROUP_INDEX},
        face_feature_indexes={MOUTH_FEATURE_INDEX},
        feature_only=True,
    )
    (ASSETS / "zito-intro-foot.svg").unlink(missing_ok=True)
    (ASSETS / "zito-intro-fallback.svg").unlink(missing_ok=True)

    lottie = _build_lottie()
    OUTPUT.write_text(json.dumps(lottie, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    json.loads(OUTPUT.read_text(encoding="utf-8"))
    print(f"Built {OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
