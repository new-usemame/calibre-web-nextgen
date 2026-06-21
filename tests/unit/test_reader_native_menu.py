"""Source-pin: the web reader suppresses the native context menu (right-click /
long-press) inside the content so the in-app highlight popup is the affordance,
WITHOUT disabling text selection (highlighting needs a live selection). Task #30.

Client-side behaviour with no Python entry point — pinned on the shipped source
like the other reader JS tests. RED on main (no suppression); GREEN on branch.
The iOS text-selection edit menu is a documented platform limit
(notes/2026-06-17-reader-native-menu-DESIGN.md) and is intentionally not asserted.
"""
import re
from pathlib import Path

import pytest

EPUB_JS = (
    Path(__file__).resolve().parents[2]
    / "cps" / "static" / "js" / "reading" / "epub.js"
)


def _src():
    return EPUB_JS.read_text(encoding="utf-8")


def test_has_suppress_helper():
    assert "suppressReaderNativeMenu" in _src()


def test_contextmenu_is_prevented():
    src = _src()
    assert re.search(r"addEventListener\(\s*['\"]contextmenu['\"]", src), "no contextmenu listener"
    assert "preventDefault" in src


def test_ios_long_press_callout_suppressed():
    assert "-webkit-touch-callout" in _src()


def test_reapplied_on_each_section_render():
    # epub.js swaps the iframe document per spine item — suppression must re-run.
    assert re.search(r"on\(\s*['\"]rendered['\"][\s\S]{0,120}suppressReaderNativeMenu", _src()), \
        "suppression not re-applied on 'rendered'"


def test_does_not_disable_text_selection():
    # The fix must NOT kill selection to remove the menu — highlighting needs it.
    # Guards against a future "iOS fix" that sets user-select:none on content.
    assert "user-select" not in _src(), "epub.js must not disable user-select (breaks highlighting)"


# --- fork #502: native context menu must stay available on images/media ----------
#
# The contextmenu suppression above blanket-prevented the menu on EVERY target,
# including <img> / SVG <image>, so right-click "Save image as" was dead in the
# web reader. The fix keeps suppression on text (highlight popup affordance) but
# lets the native menu through on image/media targets. RED on the pre-#502 source
# (blanket preventDefault), GREEN after.

import shutil
import subprocess
import textwrap


def test_contextmenu_handler_guards_image_targets_before_preventing():
    """The contextmenu handler must early-return on media targets, so the
    blanket `ev.preventDefault()` no longer runs for images."""
    src = _src()
    # The handler must consult a media-target check and have a guarded return.
    assert "isReaderMediaTarget" in src, "no media-target guard in epub.js"
    handler = re.search(
        r"addEventListener\(\s*['\"]contextmenu['\"][\s\S]*?\}\s*,\s*false\s*\)",
        src,
    )
    assert handler, "contextmenu listener not found"
    body = handler.group(0)
    assert "isReaderMediaTarget" in body, "contextmenu handler does not check the target"
    # The early return must appear before preventDefault in the handler body.
    assert "return" in body and "preventDefault" in body
    assert body.index("return") < body.index("preventDefault"), \
        "media-target return must guard preventDefault (else menu is blanket-suppressed)"


def test_touch_callout_re_enabled_on_media():
    """The global -webkit-touch-callout:none also kills the iOS long-press
    Save-Image affordance; the fix re-enables it on media elements."""
    src = _src()
    assert re.search(r"-webkit-touch-callout\s*:\s*default", src), \
        "callout not re-enabled on media for iOS long-press save"
    # the exemption selector must cover SVG <image> and HTML <img>
    assert re.search(r"image[^{]*\{[^}]*-webkit-touch-callout\s*:\s*default", src) \
        or "img,image" in src.replace(" ", ""), "callout exemption must cover img/image"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_is_reader_media_target_logic_executes():
    """Execute the real isReaderMediaTarget() helper in node against a fake
    element graph — pins the BEHAVIOR (SVG <image>, ancestor walk), not just text."""
    src = _src()
    fn = re.search(r"function isReaderMediaTarget\(node\)\s*\{[\s\S]*?\n    \}", src)
    assert fn, "isReaderMediaTarget definition not found"
    script = fn.group(0) + textwrap.dedent(
        """
        function el(name, parent) {
            return { nodeType: 1, localName: name, tagName: name, parentNode: parent || null };
        }
        const svg = el('svg');
        const svgImage = el('image', svg);   // EPUB illustrations are SVG <image>
        const htmlImg = el('img');
        const para = el('p');
        const spanInSvg = el('span', svg);   // descendant of <svg> wrapper
        const out = {
            svgImage: isReaderMediaTarget(svgImage),
            htmlImg: isReaderMediaTarget(htmlImg),
            para: isReaderMediaTarget(para),
            spanInSvg: isReaderMediaTarget(spanInSvg),
            nullTarget: isReaderMediaTarget(null),
        };
        process.stdout.write(JSON.stringify(out));
        """
    )
    proc = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    import json
    out = json.loads(proc.stdout)
    assert out["svgImage"] is True, "SVG <image> must be treated as media"
    assert out["htmlImg"] is True, "HTML <img> must be treated as media"
    assert out["para"] is False, "text <p> must NOT be treated as media (keep suppression)"
    assert out["spanInSvg"] is True, "node inside <svg> must be treated as media"
    assert out["nullTarget"] is False
