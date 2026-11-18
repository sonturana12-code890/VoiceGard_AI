"""
VOICEGUARD AI — Frontend Forensic Auditor (Built-in HTMLParser)
Extracts all buttons, links, forms, and inputs from index.html and app.html.
Cross-references with JS controller event listeners and backend endpoints.
"""

import re
import os
from html.parser import HTMLParser

class ElementExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.links = []
        self.forms = []
        self.inputs = []
        self._current_tag = None
        self._current_attrs = {}
        self._text_buffer = []

    def handle_starttag(self, tag, attrs):
        self._current_tag = tag
        attr_dict = dict(attrs)
        self._current_attrs = attr_dict
        self._text_buffer = []

        if tag == "button":
            self.buttons.append({
                "tag": tag,
                "id": attr_dict.get("id"),
                "class": attr_dict.get("class"),
                "onclick": attr_dict.get("onclick"),
                "type": attr_dict.get("type", "button"),
                "text": "",
            })
        elif tag == "a":
            self.links.append({
                "tag": tag,
                "id": attr_dict.get("id"),
                "class": attr_dict.get("class"),
                "href": attr_dict.get("href"),
                "onclick": attr_dict.get("onclick"),
                "data_view": attr_dict.get("data-view"),
                "text": "",
            })
        elif tag == "form":
            self.forms.append({
                "tag": tag,
                "id": attr_dict.get("id"),
                "action": attr_dict.get("action"),
                "method": attr_dict.get("method"),
            })
        elif tag in ["input", "select", "textarea"]:
            self.inputs.append({
                "tag": tag,
                "id": attr_dict.get("id"),
                "type": attr_dict.get("type"),
                "name": attr_dict.get("name"),
            })

    def handle_data(self, data):
        self._text_buffer.append(data.strip())

    def handle_endtag(self, tag):
        text = " ".join(filter(None, self._text_buffer))[:40]
        if tag == "button" and self.buttons:
            self.buttons[-1]["text"] = text
        elif tag == "a" and self.links:
            self.links[-1]["text"] = text
        self._current_tag = None
        self._text_buffer = []

def audit_html_file(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    parser = ElementExtractor()
    parser.feed(content)
    return {
        "buttons": parser.buttons,
        "links": parser.links,
        "forms": parser.forms,
        "inputs": parser.inputs,
    }

index_audit = audit_html_file("index.html")
app_audit = audit_html_file("app.html")

# Read all JS files
js_files = {}
for fname in ["api-client.js", "landing-controller.js", "app-controller.js", "script.js", "app-auth.js", "workspace.js"]:
    if os.path.exists(fname):
        with open(fname, "r", encoding="utf-8") as f:
            js_files[fname] = f.read()

print("=" * 70)
print(f"INDEX.HTML AUDIT: {len(index_audit['buttons'])} buttons, {len(index_audit['links'])} links, {len(index_audit['forms'])} forms")
print(f"APP.HTML AUDIT: {len(app_audit['buttons'])} buttons, {len(app_audit['links'])} links, {len(app_audit['forms'])} forms")
print("=" * 70)

# Check buttons in index.html
print("\n--- INDEX.HTML BUTTONS ---")
for b in index_audit["buttons"]:
    bid = b["id"]
    btext = b["text"]
    found = any(bid and bid in code for code in js_files.values())
    status = "BOUND" if found else "NO_DIRECT_ID_REF"
    print(f"  [{status}] ID: {bid} | Text: '{btext}' | onclick: {b.get('onclick')}")

# Check buttons in app.html
print("\n--- APP.HTML BUTTONS ---")
for b in app_audit["buttons"]:
    bid = b["id"]
    btext = b["text"]
    found_in = [name for name, code in js_files.items() if bid and bid in code]
    status = f"BOUND in {','.join(found_in)}" if found_in else "UNBOUND / UNATTACHED"
    print(f"  [{status}] ID: {bid} | Text: '{btext}' | type: {b.get('type')}")

# Check links in app.html
print("\n--- APP.HTML VIEW NAVIGATION LINKS ---")
for a in app_audit["links"]:
    aid = a["id"]
    dview = a.get("data_view")
    href = a.get("href")
    text = a.get("text")
    if dview or (href and href.startswith("#")):
        print(f"  [NAV] ID: {aid} | data-view: '{dview}' | href: '{href}' | Text: '{text}'")

# Check for TODOs, mock data, or alerts in JS files
print("\n" + "=" * 70)
print("POTENTIAL PLACEHOLDERS, ALERTS, OR MOCKS IN JAVASCRIPT")
print("=" * 70)
for js_name, js_code in js_files.items():
    todos = re.findall(r'//.*TODO.*|/\*.*TODO.*\*/', js_code, re.IGNORECASE)
    alerts = re.findall(r'alert\(.*?\)', js_code)
    if todos or alerts:
        print(f"\nFile: {js_name}")
        for t in todos[:5]:
            print(f"  [TODO] {t.strip()}")
        for a in alerts[:5]:
            print(f"  [ALERT] {a.strip()}")
