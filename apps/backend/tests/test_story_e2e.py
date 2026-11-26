#!/usr/bin/env python3
"""
Scale Lab — Story E2E Test (production path)

Runs on the VPS, uses the REAL backend modules:
  IGDriver → HumanTouch → mcp_call → iPhone MCP

Usage (from VPS):
    cd /root/scale-lab/apps/backend
    python3 -m tests.test_story_e2e [action]

Actions:
    open        Open story editor from profile
    poll        Add poll sticker (2 options)
    question    Add question sticker
    link        Add link sticker
    mention     Add mention sticker
    location    Add location sticker
    music       Add music sticker
    text        Add text sticker
    publish     Publish the story
    highlight   Add to highlight (from story view)
    dump        Dump UI elements
    ocr         OCR screen
    screenshot  Take screenshot
    e2e         Full E2E: open → link → publish
    menu        Interactive menu
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.services.automation.ig_driver import IGDriver
from app.services.automation.ig_iphone.interact.story_stickers import (
    open_story_editor,
    add_poll_sticker,
    add_question_sticker,
    add_link_sticker,
    add_location_sticker,
    add_mention_sticker,
    add_music_sticker,
    add_text_sticker,
    publish_story,
    add_to_highlight,
)

# MCP port exposed by the SSH tunnel
MCP_PORT = 18090


def log(msg):
    print(msg, flush=True)


async def make_driver():
    """Create an IGDriver pointing at the local MCP tunnel."""
    driver = IGDriver(mcp_port=MCP_PORT, host="127.0.0.1", log=log)
    return driver


async def do_dump(driver):
    """Dump current UI elements."""
    await driver.refresh_elements()
    for i, el in enumerate(driver.elements()):
        txt = el.get('text', '') or '(no text)'
        tap = el.get('tap', {})
        print(f"  {i:3d}  ({tap.get('x',0):3.0f},{tap.get('y',0):3.0f})  {txt[:60]}")


async def do_ocr(driver):
    """OCR the screen."""
    result = await driver.ht._call("ocr_screen")
    if result:
        import json
        content = result.get("content", [])
        if content and isinstance(content, list):
            data = json.loads(content[0].get("text", "{}"))
            for item in data.get("texts", []):
                tap = item.get("tap", {})
                print(f"  ({tap.get('x',0):3.0f},{tap.get('y',0):3.0f})  [{item.get('confidence',0):.1f}]  {item.get('text','')[:50]}")


async def do_screenshot(driver):
    """Take and save screenshot."""
    result = await driver.ht._call("screenshot")
    if result:
        import json
        import base64
        content = result.get("content", [])
        if content:
            for c in content:
                if c.get("type") == "image":
                    img = base64.b64decode(c["data"])
                    path = "/tmp/ig_e2e_screenshot.jpg"
                    with open(path, "wb") as f:
                        f.write(img)
                    print(f"  Screenshot saved: {path}")


async def do_e2e(driver):
    """Full E2E: open editor → add link sticker → publish."""
    print("\n🚀 FULL E2E: open → link → publish")
    print("=" * 50)

    ok = await open_story_editor(driver, media_index=0, log=log)
    if not ok:
        print("❌ Failed to open story editor")
        return

    await asyncio.sleep(1)
    ok = await add_link_sticker(driver, url="https://example.com", log=log)
    if not ok:
        print("❌ Failed to add link sticker")

    await asyncio.sleep(1)
    ok = await publish_story(driver, log=log)
    if ok:
        print("✅ Story published!")
    else:
        print("❌ Failed to publish")


async def interactive_menu(driver):
    """Interactive menu for step-by-step testing."""
    while True:
        print("\n═══════════════════════════════════════")
        print("  Story E2E — Production Code Test")
        print("═══════════════════════════════════════")
        print("  1) Open story editor")
        print("  2) Add poll sticker")
        print("  3) Add question sticker")
        print("  4) Add link sticker")
        print("  5) Add mention sticker")
        print("  6) Add location sticker")
        print("  7) Add music sticker")
        print("  8) Add text sticker")
        print("  p) Publish story")
        print("  h) Add to highlight")
        print("  ---")
        print("  d) Dump UI")
        print("  o) OCR screen")
        print("  s) Screenshot")
        print("  E) Full E2E")
        print("  q) Quit")
        print("═══════════════════════════════════════")

        try:
            choice = input("  Choix: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        try:
            if choice == '1':
                await open_story_editor(driver, log=log)
            elif choice == '2':
                await add_poll_sticker(driver, question="Quelle team ?",
                                       options=["Team A", "Team B"], log=log)
            elif choice == '3':
                await add_question_sticker(driver,
                                            question="Posez-moi une question", log=log)
            elif choice == '4':
                await add_link_sticker(driver, url="https://example.com", log=log)
            elif choice == '5':
                await add_mention_sticker(driver, username="instagram", log=log)
            elif choice == '6':
                await add_location_sticker(driver, location="Paris", log=log)
            elif choice == '7':
                await add_music_sticker(driver, log=log)
            elif choice == '8':
                await add_text_sticker(driver, text="Hello World", log=log)
            elif choice == 'p':
                await publish_story(driver, log=log)
            elif choice == 'h':
                name = input("  Highlight name (Enter='Test'): ").strip() or "Test"
                await add_to_highlight(driver, highlight_name=name,
                                        create_new=True, log=log)
            elif choice == 'd':
                await do_dump(driver)
            elif choice == 'o':
                await do_ocr(driver)
            elif choice == 's':
                await do_screenshot(driver)
            elif choice == 'E':
                await do_e2e(driver)
            elif choice == 'q':
                break
            else:
                print("  ?")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()


async def main():
    driver = await make_driver()

    if len(sys.argv) < 2 or sys.argv[1] == "menu":
        await interactive_menu(driver)
        return

    action = sys.argv[1]

    if action == "open":
        await open_story_editor(driver, log=log)
    elif action == "poll":
        await add_poll_sticker(driver, question="Quelle team ?",
                               options=["Team A", "Team B"], log=log)
    elif action == "question":
        await add_question_sticker(driver,
                                    question="Posez-moi une question", log=log)
    elif action == "link":
        await add_link_sticker(driver, url="https://example.com", log=log)
    elif action == "mention":
        await add_mention_sticker(driver, username="instagram", log=log)
    elif action == "location":
        await add_location_sticker(driver, location="Paris", log=log)
    elif action == "music":
        await add_music_sticker(driver, log=log)
    elif action == "text":
        await add_text_sticker(driver, text="Hello World", log=log)
    elif action == "publish":
        await publish_story(driver, log=log)
    elif action == "highlight":
        name = sys.argv[2] if len(sys.argv) > 2 else "Test"
        await add_to_highlight(driver, highlight_name=name,
                                create_new=True, log=log)
    elif action == "dump":
        await do_dump(driver)
    elif action == "ocr":
        await do_ocr(driver)
    elif action == "screenshot":
        await do_screenshot(driver)
    elif action == "e2e":
        await do_e2e(driver)
    else:
        print(f"Unknown action: {action}")
        print("Available: open poll question link mention location music text publish highlight dump ocr screenshot e2e menu")


if __name__ == "__main__":
    asyncio.run(main())
