# review-findings.md

*Written by Sentinel — WARN-tier findings.*

## [WARN] P1-unpopulated-placeholder
- **Location:** `tower_js/src/ui_template.html:429`
- **Detail:** pattern matched: {{INLINE_SCRIPTS}}
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.047443+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:341`
- **Detail:** pattern matched: <span class="card-id">${{item.card_id}}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063386+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:342`
- **Detail:** pattern matched: <span class="badge ${{item.pain >= 60 ? 'yellow' : item.pain >= 100 ? 'red' : 'green'}}">${{item.reason}}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063399+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:345`
- **Detail:** pattern matched: Stream: ${{item.stream}} | Agent: ${{item.agent || 'unknown'}} | Last HB: ${{item.last_heartbeat || 'N/A'}}
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063404+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:359`
- **Detail:** pattern matched: <span class="card-id">${{item.card_id}}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063415+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:363`
- **Detail:** pattern matched: <code style="flex: 1; background: var(--accent); padding: 0.5rem; border-radius: 4px; font-size: 0.85rem;">${{item.merge
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063422+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:364`
- **Detail:** pattern matched: <button class="btn" onclick="navigator.clipboard.writeText('${{item.merge_cmd}}').then(() => this.textContent = 'Copied!
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063426+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:388`
- **Detail:** pattern matched: <tr><td>${{c.card_id}}</td><td>${{c.stream}}</td><td>${{c.state}}</td><td>${{c.agent}}</td><td>${{c.machine}}</td></tr>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063442+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:403`
- **Detail:** pattern matched: <div style="display:flex;justify-content:space-between"><strong>${{model}}</strong><span>${{pct.toFixed(1)}}%</span></di
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063455+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:404`
- **Detail:** pattern matched: <div class="quota-bar"><div class="quota-fill ${{barClass}}" style="width:${{Math.min(pct,100)}}%"></div></div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063459+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:414`
- **Detail:** pattern matched: <div style="display:flex;justify-content:space-between"><strong>${{name}}</strong><span class="badge ${{statusColor}}">$
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063471+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `scripts/tower_dashboard.py:447`
- **Detail:** pattern matched: <tr><td>${{p.paper_id}}</td><td>${{p.title}}</td><td>${{p.status}}</td><td>${{p.venue || '-'}}</td></tr>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.063499+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:125`
- **Detail:** pattern matched: <div class="card-item" onclick="viewCard('{{ card.card_id }}')">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069117+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:126`
- **Detail:** pattern matched: <div class="card-id">{{ card.card_id }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069130+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:137`
- **Detail:** pattern matched: <div class="card-item" onclick="viewCard('{{ card.card_id }}')">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069141+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:138`
- **Detail:** pattern matched: <div class="card-id">{{ card.card_id }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069145+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:140`
- **Detail:** pattern matched: <div class="card-state">{{ card.state }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069150+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:150`
- **Detail:** pattern matched: <div class="card-item" onclick="viewCard('{{ card.card_id }}')">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069160+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:151`
- **Detail:** pattern matched: <div class="card-id">{{ card.card_id }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069164+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:162`
- **Detail:** pattern matched: <div class="card-item" onclick="viewCard('{{ card.card_id }}')">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069174+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:163`
- **Detail:** pattern matched: <div class="card-id">{{ card.card_id }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069178+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:166`
- **Detail:** pattern matched: <button onclick="event.stopPropagation(); runGatecheck('{{ card.card_id }}')" class="btn btn-small">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069184+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:179`
- **Detail:** pattern matched: <div class="card-item" onclick="viewCard('{{ card.card_id }}')">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069194+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:180`
- **Detail:** pattern matched: <div class="card-id">{{ card.card_id }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069198+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:191`
- **Detail:** pattern matched: <div class="card-item blocked" onclick="viewCard('{{ card.card_id }}')">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069208+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:192`
- **Detail:** pattern matched: <div class="card-id">{{ card.card_id }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069212+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/index.html:194`
- **Detail:** pattern matched: <div class="card-state">{{ card.state }}</div>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.069217+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/autoclaude/prompt_registry.py:82`
- **Detail:** pattern matched: result = result.replace(f"{{{var}}}", str(value))
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.086843+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/README_DASHBOARD_ADDON.md:119`
- **Detail:** pattern matched: | `{{STATUS}}` | Status text (GREEN, YELLOW, etc.) |
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.087491+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/README_DASHBOARD_ADDON.md:120`
- **Detail:** pattern matched: | `{{STATUS_LOWER}}` | Lowercase status for CSS classes |
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.087500+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/README_DASHBOARD_ADDON.md:121`
- **Detail:** pattern matched: | `{{ERROR_BUDGET_REMAINING}}` | Remaining budget with % |
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.087504+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/README_DASHBOARD_ADDON.md:122`
- **Detail:** pattern matched: | `{{SLO_STATUS}}` | SLO status text |
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.087507+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/README_DASHBOARD_ADDON.md:123`
- **Detail:** pattern matched: | `{{ACTIVE_CARDS}}` | Count of active cards |
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.087511+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/README_DASHBOARD_ADDON.md:124`
- **Detail:** pattern matched: | `{{ALERT_TAGS}}` | HTML for alert indicator tags |
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.087515+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/README_DASHBOARD_ADDON.md:125`
- **Detail:** pattern matched: | `{{TIMESTAMP}}` | ISO timestamp |
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.087518+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:129`
- **Detail:** pattern matched: <div class="resilience-panel status-{{STATUS_LOWER}}">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093461+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:130`
- **Detail:** pattern matched: <div class="resilience-badge badge-{{STATUS_LOWER}}">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093472+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:132`
- **Detail:** pattern matched: {{STATUS}}
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093478+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:138`
- **Detail:** pattern matched: <span class="resilience-metric-value">{{ERROR_BUDGET_REMAINING}}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093485+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:142`
- **Detail:** pattern matched: <span class="resilience-metric-value">{{SLO_STATUS}}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093491+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:146`
- **Detail:** pattern matched: <span class="resilience-metric-value">{{ACTIVE_CARDS}}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093496+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:151`
- **Detail:** pattern matched: {{ALERT_TAGS}}
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093502+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/resilience/templates/resilience_panel_template.html:154`
- **Detail:** pattern matched: <span class="resilience-timestamp">Updated: {{TIMESTAMP}}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.093507+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/autoclaude/metrics_exporter.py:107`
- **Detail:** pattern matched: lines.append(f"{self.name}_bucket{{{label_str}}} {bucket.count}")
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.094193+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/autoclaude/metrics_exporter.py:117`
- **Detail:** pattern matched: lines.append(f"{self.name}{{{label_str}}} {mv.value}")
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.094208+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:6`
- **Detail:** pattern matched: <title>{{ card.card_id }} - Tower</title>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104750+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:12`
- **Detail:** pattern matched: <h1>{{ card.card_id }}</h1>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104764+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:13`
- **Detail:** pattern matched: <span class="state-badge {{ card.state|lower }}">{{ card.state }}</span>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104770+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:22`
- **Detail:** pattern matched: <td>{{ card.card_id }}</td>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104777+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:30`
- **Detail:** pattern matched: <td><span class="state-badge {{ card.state|lower }}">{{ card.state }}</span></td>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104785+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:51`
- **Detail:** pattern matched: <td class="escalation">{{ card.escalation_reason }}</td>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104801+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:62`
- **Detail:** pattern matched: <button onclick="runGatecheck('{{ card.card_id }}')" class="btn btn-primary">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104810+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:67`
- **Detail:** pattern matched: <button onclick="runValidateCard('{{ card.card_id }}')" class="btn btn-secondary">
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104816+00:00

## [WARN] P1-unpopulated-placeholder
- **Location:** `addons/gui/templates/card_detail.html:90`
- **Detail:** pattern matched: <td class="event-type">{{ event.type }}</td>
- **Fix hint:** Populate the placeholder or escape it before shipping. If the braces are intentional template syntax in a non-template file, exclude the file path via the rule's exclude list.

- **Source:** html-apps.md#safety-checks
- **When:** 2026-04-15T02:08:46.104831+00:00
