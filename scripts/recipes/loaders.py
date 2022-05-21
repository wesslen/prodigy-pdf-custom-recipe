import base64
import json
from pathlib import Path
from typing import Dict, List, Union

from wasabi import msg

from scripts.constants import TRAIN_IMAGES, TRAIN_LABELS

try:
    import prodigy
    from prodigy import set_hashes
    from prodigy.components.db import connect
except ImportError:
    msg.fail("No installation of prodigy found")
    raise


def _bbox_to_poly(bbox: List) -> List[List[int]]:
    """Convert bounding box into polygon coordinates"""
    x_left, y_top, x_right, y_bottom = bbox
    return [
        [x_left, y_top],
        [x_right, y_top],
        [x_right, y_bottom],
        [x_left, y_bottom],
    ]


def _create_task(file_id: str, answer: str = "accept", encode_b64: bool = True) -> Dict:
    """Create a Prodigy task dictionary given a file ID

    Since we already have annotations, we will be following the image.manual
    task format: https://prodi.gy/docs/api-interfaces#image_manual
    """
    # Load the image and get its b64 representation if needed
    image_fp = TRAIN_IMAGES / f"{file_id}.png"
    with open(image_fp, "rb") as f:
        img = f.read()
    source_img = (
        base64.encodebytes(img).decode("utf-8") if encode_b64 else str(image_fp)
    )

    # Format the annotations
    annot_fp = TRAIN_LABELS / f"{file_id}.json"
    with open(annot_fp) as f:
        annot = json.load(f)
    spans = [
        {"points": _bbox_to_poly(a["box"]), "label": a["label"]} for a in annot["form"]
    ]

    task = set_hashes({"image": source_img, "spans": spans, "answer": answer})
    return task


@prodigy.recipe(
    "db-in-image",
    # fmt: off
    set_id=("Dataset to import annotations to", "positional", None, str),
    answer=("Set this answer key if none is present", "option", "a", str),
    encode_b64=("Encode to base64 before storing to db", "flag", "e", bool)
    # fmt: on
)
def db_in_image(
    set_id: str,
    answer: str = "accept",
    encode_b64: bool = False,
):
    """Import annotations to the database

    This assumes that the filename of the annotations is the same as the
    filename of the images. The images can be encoded into their base-64
    representation and then saved to the database.
    """

    # Get all file IDs
    files = TRAIN_IMAGES.glob("**/*")
    file_ids = [f.stem for f in files if f.is_file()]
    msg.info(f"Found {len(file_ids)} images and annotations")

    # For each file ID, prepare the sample and format
    # them to Prodigy's task format as seen in this link:
    # https://prodi.gy/docs/api-interfaces#image_manual
    if encode_b64:
        msg.info("Encoding images into their base64 representation")
    examples = [_create_task(_id, answer, encode_b64) for _id in file_ids]

    db = connect()
    db.add_dataset(set_id)
    db.add_examples(examples, [set_id])
