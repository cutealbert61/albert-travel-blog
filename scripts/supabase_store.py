#!/usr/bin/env python3
"""Supabase document, media and release helpers for the travel blog."""

import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path

import requests

SUPABASE_URL = "https://yjdogvojaeerbedqjznz.supabase.co"
ADMIN_ENDPOINT = SUPABASE_URL + "/functions/v1/travel-blog-admin"
WRITE_TOKEN = os.environ.get("TRAVEL_BLOG_WRITE_TOKEN", "")


def _call_admin(payload, timeout=180):
    if not WRITE_TOKEN:
        raise RuntimeError("缺少 TRAVEL_BLOG_WRITE_TOKEN")
    response = requests.post(
        ADMIN_ENDPOINT,
        headers={
            "content-type": "application/json",
            "x-blog-write-token": WRITE_TOKEN,
        },
        json=payload,
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            "Supabase 管理 API 失敗 "
            + str(response.status_code)
            + ": "
            + response.text[:500]
        )
    return response.json()


def load_document(key):
    return _call_admin({"action": "read_document", "key": key})["payload"]


def save_document(key, payload):
    return _call_admin({"action": "write_document", "key": key, "payload": payload})


def import_image_url(source_url):
    if source_url.startswith(
        SUPABASE_URL + "/storage/v1/object/public/travel-blog-media/"
    ):
        return source_url
    return _call_admin(
        {"action": "import_url", "source_url": source_url},
        timeout=240,
    )["public_url"]


def upload_release(root, version_label):
    root = Path(root)
    archive = root / (version_label + ".zip")
    subprocess.run(
        ["git", "archive", "--format=zip", "--output", str(archive), "HEAD"],
        cwd=root,
        check=True,
    )
    try:
        payload = archive.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        file_count = len(
            subprocess.check_output(
                ["git", "ls-tree", "-r", "--name-only", "HEAD"],
                cwd=root,
                text=True,
            ).splitlines()
        )
        result = _call_admin(
            {
                "action": "upload_backup",
                "name": archive.name,
                "content_type": "application/zip",
                "base64": base64.b64encode(payload).decode("ascii"),
                "release": {
                    "version_label": version_label,
                    "commit_sha": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=root, text=True
                    ).strip(),
                    "file_count": file_count,
                    "size_bytes": len(payload),
                    "sha256": digest,
                    "manifest": {
                        "storage": "supabase",
                        "format": "git-archive-zip",
                    },
                },
            },
            timeout=300,
        )
        return result
    finally:
        archive.unlink(missing_ok=True)


if __name__ == "__main__":
    command = os.environ.get("TRAVEL_BLOG_COMMAND", "health")
    if command == "health":
        print(json.dumps(_call_admin({"action": "health"}), ensure_ascii=False))
    elif command == "backup":
        root = Path(__file__).resolve().parent.parent
        label = os.environ.get("TRAVEL_BLOG_VERSION_LABEL") or "release-" + subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=root, text=True
        ).strip()
        print(json.dumps(upload_release(root, label), ensure_ascii=False))
    else:
        raise SystemExit("不支援的 TRAVEL_BLOG_COMMAND: " + command)
