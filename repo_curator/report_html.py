"""Render a compact, self-contained HTML view of one audit brief."""

import html
from collections import defaultdict
from typing import Any, Dict, Iterable, Mapping, Sequence


_MAX_FOLDER_ROWS = 256


def render_temporary_audit_html(
    brief: Mapping[str, Any],
    inventory_records: Iterable[Mapping[str, Any]],
    brief_sha256: str,
) -> str:
    """Render HTML from verified brief data without adding new conclusions."""
    folders, root_files = _top_level_summary(inventory_records)
    scope = brief["audit_scope"]
    observed = brief["observed_evidence"]
    risks = brief["preservation_risks"]
    attention = brief["review_attention_items"]
    questions = brief["decision_questions"]
    status, status_class = _status(brief)
    title = f"repo-curator audit · {brief['run_id']}"
    body = [
        '<main class="shell">',
        '  <header class="hero">',
        f'    <div><p class="eyebrow">REPO-CURATOR · READ-ONLY AUDIT</p><h1>临时审计报告</h1><p class="muted">{_esc(scope["repository_root_realpath"])}</p></div>',
        f'    <div class="status {status_class}">{_esc(status)}</div>',
        '  </header>',
        '  <div class="toolbar"><button type="button" onclick="window.print()">打印 / 保存为 PDF</button></div>',
        '  <section class="notice"><strong>安全边界</strong> 本报告只展示已生成的审计证据，不执行代码、Notebook 或工作流，也不授权删除、移动或合并文件。</section>',
        '  <section class="metrics">',
        _metric("发现对象", scope["artifact_count"], "个"),
        _metric("重复文件组", observed["exact_byte_duplicate_group_count"], "组"),
        _metric("需要复核", len(attention) + len(questions), "项"),
        _metric("未解决对象", risks["unresolved_artifact_count"], "个"),
        '  </section>',
        f'  <section class="panel"><div class="section-head"><div><p class="eyebrow">优先处理</p><h2>需要人工查看</h2></div><span class="count">{len(attention) + len(questions)}</span></div>',
        _attention_html(attention, questions),
        '  </section>',
        '  <section class="panel"><div class="section-head"><div><p class="eyebrow">仓库结构</p><h2>根目录文件夹</h2></div><span class="muted">次要参考</span></div>',
        '    <p class="muted small">大小按已盘点的普通文件递归汇总；不跟随符号链接，不包含 .repo-curator 控制目录。</p>',
        _folder_table(folders, root_files),
        '  </section>',
        '  <section class="grid-two">',
        _facts_html(brief),
        _limitations_html(risks["warnings"]),
        '  </section>',
        f'  <section class="next"><p class="eyebrow">下一步</p><h2>{_esc(_next_title(brief))}</h2><p>{_esc(_next_reason(brief))}</p></section>',
        f'  <footer>运行 ID：<code>{_esc(brief["run_id"])}</code> · brief SHA-256：<code>{_esc(brief_sha256)}</code></footer>',
        '</main>',
    ]
    return _document(title, "\n".join(body))


def _document(title: str, body: str) -> str:
    css = """:root{color-scheme:light;--ink:#172033;--muted:#667085;--line:#e4e7ec;--surface:#fff;--wash:#f6f8fb;--blue:#2952cc;--amber:#a15c00;--amber-bg:#fff6e5;--green:#16724a;--green-bg:#eaf8f0;--shadow:0 8px 26px rgba(16,24,40,.06)}*{box-sizing:border-box}body{margin:0;background:var(--wash);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.shell{max-width:1080px;margin:0 auto;padding:38px 22px 56px}.hero{display:flex;gap:24px;align-items:flex-start;justify-content:space-between;margin-bottom:12px}h1,h2,p{margin:0}h1{font-size:31px;letter-spacing:-.03em}h2{font-size:19px}.eyebrow{color:var(--blue);font-size:11px;font-weight:750;letter-spacing:.12em;margin-bottom:6px}.muted{color:var(--muted)}.small{font-size:13px}.status{border-radius:999px;font-weight:700;padding:8px 14px;white-space:nowrap}.status.review{background:var(--amber-bg);color:var(--amber)}.status.ok{background:var(--green-bg);color:var(--green)}.status.limited{background:#eef2ff;color:#3448a5}.toolbar{display:flex;justify-content:flex-end;margin-bottom:18px}.toolbar button{background:var(--surface);border:1px solid var(--line);border-radius:8px;color:var(--ink);cursor:pointer;font:inherit;font-size:13px;padding:7px 11px}.toolbar button:hover{border-color:#aab8d9}.notice{background:#eef4ff;border:1px solid #cfdbff;border-radius:12px;color:#28427f;margin-bottom:18px;padding:13px 15px}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}.metric,.panel,.next{background:var(--surface);border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}.metric{padding:17px}.metric-value{font-size:28px;font-weight:750}.metric-label{color:var(--muted);font-size:13px}.metric-unit{font-size:13px;font-weight:500;margin-left:4px}.panel{padding:20px;margin-bottom:18px}.section-head{align-items:center;display:flex;justify-content:space-between;margin-bottom:13px}.count{background:#f0f2f5;border-radius:999px;color:#475467;font-size:13px;font-weight:700;padding:4px 9px}.attention{border-left:4px solid #e09b2d;background:#fffbf3;border-radius:8px;margin:9px 0;padding:11px 13px}.attention strong{display:block}.reason{color:var(--muted);font-size:13px}.empty{color:var(--muted);padding:5px 0}.table-wrap{overflow:auto}.folder-table{border-collapse:collapse;min-width:620px;width:100%}.folder-table th,.folder-table td{border-bottom:1px solid var(--line);padding:10px 8px;text-align:left}.folder-table th{color:var(--muted);font-size:12px}.folder-table td:not(:first-child),.folder-table th:not(:first-child){text-align:right}.folder-table tr:last-child td{border-bottom:0}.folder-name{font-weight:650}.grid-two{display:grid;grid-template-columns:1fr 1fr;gap:18px}.list{list-style:none;margin:0;padding:0}.list li{border-bottom:1px solid var(--line);padding:9px 0}.list li:last-child{border:0}.next{background:#172033;color:#fff;padding:21px 22px}.next .eyebrow{color:#9db6ff}.next p{color:#d5dbea}.next h2{margin-bottom:5px}footer{color:var(--muted);font-size:12px;margin-top:22px}@media(max-width:720px){.shell{padding:25px 14px 40px}.hero{display:block}.status{display:inline-block;margin-top:14px}.metrics{grid-template-columns:repeat(2,1fr)}.grid-two{grid-template-columns:1fr}}@media print{body{background:#fff}.shell{max-width:none;padding:0}.toolbar{display:none}.metric,.panel,.next{box-shadow:none;break-inside:avoid}.next{color:#000;border:1px solid var(--line);background:#fff}.next .eyebrow,.next p{color:var(--ink)}a{color:inherit;text-decoration:none}}"""
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_esc(title)}</title><style>{css}</style></head><body>{body}</body></html>\n'


def _metric(label: str, value: Any, unit: str) -> str:
    return f'<div class="metric"><div class="metric-value">{_esc(value)}<span class="metric-unit">{_esc(unit)}</span></div><div class="metric-label">{_esc(label)}</div></div>'


def _attention_html(items: Sequence[Mapping[str, Any]], questions: Sequence[Mapping[str, Any]]) -> str:
    if not items and not questions:
        return '<p class="empty">没有发现需要立即人工处理的项目。</p>'
    rows = []
    for item in items[:8]:
        paths = "、".join(f"<code>{_esc(path)}</code>" for path in item["repository_relative_paths"])
        rows.append(f'<div class="attention"><strong>{_esc(_label(item["recommendation_type"]))} · {paths}</strong><span class="reason">{_esc(_reason(item))}</span></div>')
    for question in questions[:8]:
        affected = "、".join(f"<code>{_esc(path)}</code>" for path in question.get("affected_artifacts", [])) or "相关证据"
        rows.append(f'<div class="attention"><strong>需要确认证据 · {affected}</strong><span class="reason">{_esc(question.get("exact_decision", "请确认相关证据"))}</span></div>')
    omitted = max(len(items) - 8, 0) + max(len(questions) - 8, 0)
    if omitted:
        rows.append(f'<p class="muted small">另有 {omitted} 项复核内容保留在完整 brief 中，本页只展示前 8 项。</p>')
    return "\n".join(rows)


def _folder_table(folders: Mapping[str, Mapping[str, int]], root_files: Mapping[str, int]) -> str:
    rows = []
    ordered = sorted(folders.items(), key=lambda item: (-item[1]["bytes"], item[0]))
    for name, values in ordered[:_MAX_FOLDER_ROWS]:
        rows.append(f'<tr><td class="folder-name">{_esc(name)}/</td><td>{_esc(_size(values["bytes"]))}</td><td>{values["files"]}</td><td>{values["items"]}</td></tr>')
    omitted = len(ordered) - min(len(ordered), _MAX_FOLDER_ROWS)
    if omitted:
        rows.append(f'<tr><td colspan="4" class="muted">另有 {omitted} 个一级文件夹未展开，完整对象清单仍保留在 inventory.jsonl。</td></tr>')
    if root_files["files"]:
        rows.append(f'<tr><td class="folder-name">根目录文件</td><td>{_esc(_size(root_files["bytes"]))}</td><td>{root_files["files"]}</td><td>{root_files["items"]}</td></tr>')
    if not rows:
        return '<p class="empty">没有可汇总的一级文件夹。</p>'
    return '<div class="table-wrap"><table class="folder-table"><thead><tr><th>位置</th><th>大小</th><th>文件数</th><th>对象数</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'


def _top_level_summary(records: Iterable[Mapping[str, Any]]) -> tuple[Dict[str, Dict[str, int]], Dict[str, int]]:
    folders: Dict[str, Dict[str, int]] = defaultdict(lambda: {"bytes": 0, "files": 0, "items": 0})
    root_files = {"bytes": 0, "files": 0, "items": 0}
    for record in records:
        path = str(record.get("repository_relative_path", ""))
        if path in {"", "."}:
            continue
        is_file = record.get("object_type") == "REGULAR_FILE"
        size = record.get("size_bytes") if is_file else 0
        size = size if isinstance(size, int) and size >= 0 else 0
        target = root_files if "/" not in path else folders[path.split("/", 1)[0]]
        target["items"] += 1
        target["bytes"] += size
        target["files"] += int(is_file)
    return dict(folders), root_files


def _facts_html(brief: Mapping[str, Any]) -> str:
    intent = brief["project_intent"]
    chains = brief["declared_experiment_chains"]
    risks = brief["preservation_risks"]
    return '<section class="panel"><div class="section-head"><div><p class="eyebrow">事实摘要</p><h2>目前能确认什么</h2></div></div><ul class="list"><li>项目意图：<strong>{}</strong></li><li>实验链：完整 {} 个，不完整 {} 个</li><li>证据缺口：{} 个</li><li>审计只观察内容，不执行目标项目</li></ul></section>'.format(_esc(_intent(intent["status"])), chains["complete_bundle_count"], chains["incomplete_bundle_count"], risks["reproducibility_gap_count"])


def _limitations_html(warnings: Sequence[str]) -> str:
    values = "".join(f'<li>{_esc(_limitation(item))}</li>' for item in warnings[:8]) or '<li>没有额外范围限制</li>'
    return f'<section class="panel"><div class="section-head"><div><p class="eyebrow">证据边界</p><h2>仍然不确定</h2></div></div><ul class="list">{values}</ul></section>'


def _status(brief: Mapping[str, Any]) -> tuple[str, str]:
    if brief["decision_questions"] or brief["review_attention_items"]:
        return "需要人工复核", "review"
    if brief["preservation_risks"]["warnings"]:
        return "已完成 · 有范围限制", "limited"
    return "未发现立即处理项", "ok"


def _next_title(brief: Mapping[str, Any]) -> str:
    if brief["decision_questions"]:
        return "先回答证据问题"
    if brief["review_attention_items"]:
        return "先查看优先复核项"
    return "暂时保留并记录本次审计"


def _next_reason(brief: Mapping[str, Any]) -> str:
    if brief["decision_questions"]:
        return "冲突或缺失证据可能改变保留策略，先确认事实再整理。"
    if brief["review_attention_items"]:
        return "审计只提出候选，不会自动修改仓库。"
    return "当前没有足够理由执行整理动作。"


def _label(value: str) -> str:
    return {"MANUAL_REVIEW": "人工复核", "REVIEW_EXACT_DUPLICATE": "检查重复文件", "ARCHIVE": "检查归档候选", "MERGE": "检查合并候选"}.get(value, value)


def _reason(item: Mapping[str, Any]) -> str:
    if item["recommendation_type"] == "REVIEW_EXACT_DUPLICATE":
        return "内容相同，但相同内容不能证明用途相同，因此不会自动删除。"
    if "NON_REGULAR_ARTIFACT_PRESERVED" in item.get("limitations", []):
        return "这是链接或其他非普通文件对象，需要确认目标和用途。"
    return "证据不足以安全决定保留、移动或删除。"


def _intent(value: str) -> str:
    return {"UNRESOLVED": "尚未确认", "SUPPORTED": "已有证据支持", "PARTIAL": "部分确认"}.get(value, value)


def _limitation(value: str) -> str:
    return {"GIT_NOT_REPOSITORY": "目标不是 Git 仓库，无法提供提交历史证据。", "INTENT_UNRESOLVED": "项目意图或主线证据不足。", "SYMLINK_TARGET_MISSING": "存在目标缺失的符号链接。", "DVC_COMMANDS_NOT_EXECUTED": "DVC 命令没有执行，只观察了声明。", "DVC_YAML_LEXICAL_ONLY": "DVC 文件只做了有限词法观察。", "MLFLOW_PROJECT_NOT_EXECUTED": "MLflow 项目没有执行。", "MLFLOW_METADATA_KEYS_ONLY": "MLflow 只保留了有限 metadata 信息。"}.get(value, f"存在范围限制：{value}。")


def _size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1000 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1000
    return f"{size:.1f} TB"


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)
