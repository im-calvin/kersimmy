"""Theme controls and palette shared by the generated draft and review readers."""

from pathlib import Path

SCRIPT = (Path(__file__).resolve().parent.parent / 'web' / 'theme.js').read_text(encoding='utf-8')
CONTROL = '<button type="button" class="theme-toggle" aria-label="Switch theme">☾</button>'

CSS = """
:root{color-scheme:light;--ink:#1b1a17;--dim:#a8a29a;--bg:#faf8f4;--line:#eae5dc;
  --surface:#fffefb;--control:#fff;--hover:#f0ebe2;--subtle:#f1ece2;
  --heading:#6b6455;--volume:#8c8375;--placeholder:#cfc8bc;
  --accent:#8a6f12;--accent-line:#c9a227;--accent-soft:#f6efdc;--reading:#fdf4d8;--review-hit:#fff3b0;
  --error:#a2392a;--error-bg:#fff0e8;--status:#425b48;--status-bg:#f1f2e9;
  --scrim:#28332365;--glossary:#be3535;--comment-link:#6d4294}
:root[data-theme="dark"]{color-scheme:dark;--ink:#e8d6b8;--dim:#b4ab9d;--bg:#201f22;--line:#443f41;
  --surface:#19181c;--control:#29272c;--hover:#383339;--subtle:#302c31;
  --heading:#cec0af;--volume:#b7a891;--placeholder:#aaa197;
  --accent:#e4c174;--accent-line:#b99755;--accent-soft:#3e3323;--reading:#3d3222;--review-hit:#473821;
  --error:#ffa49b;--error-bg:#402628;--status:#abd0b6;--status-bg:#242f29;
  --scrim:#08070bb3;--glossary:#f28782;--comment-link:#ccaae9}
a{color:var(--heading)}
button.theme-toggle{color:var(--heading);font-size:20px;line-height:1;width:32px;height:32px;padding:0}
"""
