"""Graphiques SVG des alertes, générés côté serveur sans dépendance JavaScript."""

from dataclasses import dataclass

from markupsafe import Markup

ALERT_SEVERITY_GROUPS = (
    ("Critique", "critical", "#c63f68"),
    ("Moyenne", "medium", "#d69a27"),
    ("Faible", "low", "#36947c"),
)
CHART_WIDTH = 420
BAR_CHART_HEIGHT = 190
DONUT_CHART_SIZE = 180
DONUT_CENTER = DONUT_CHART_SIZE / 2
DONUT_RADIUS = 56
DONUT_CIRCUMFERENCE = 2 * 3.141592653589793 * DONUT_RADIUS


@dataclass(frozen=True)
class AlertSeverityCounts:
    """Nombre d'alertes dans les trois groupes affichés dans l'interface."""

    critical: int
    medium: int
    low: int

    @property
    def total(self) -> int:
        """Retourne le nombre total d'alertes réparties dans les groupes."""
        return self.critical + self.medium + self.low


@dataclass(frozen=True)
class AlertChartSvgs:
    """Graphiques de répartition par sévérité destinés au gabarit Alertes."""

    bars: Markup
    donut: Markup


def build_alert_chart_svgs(alert_counts: AlertSeverityCounts) -> AlertChartSvgs:
    """Construit les graphiques en barres et circulaire de la page Alertes."""
    return AlertChartSvgs(
        bars=_build_alert_bar_chart_svg(alert_counts),
        donut=_build_alert_donut_chart_svg(alert_counts),
    )


def _build_alert_bar_chart_svg(alert_counts: AlertSeverityCounts) -> Markup:
    values = (alert_counts.critical, alert_counts.medium, alert_counts.low)
    maximum_value = max(max(values), 1)
    baseline = 139
    maximum_bar_height = 94
    bar_width = 62
    bar_positions = (56, 179, 302)
    svg_parts = [
        f'<svg class="alert-bar-chart" viewBox="0 0 {CHART_WIDTH} {BAR_CHART_HEIGHT}" role="img" '
        'aria-label="Nombre d’alertes par niveau de sévérité">',
        f'<line x1="30" x2="390" y1="{baseline}" y2="{baseline}" class="alert-chart-axis" />',
    ]

    for (label, _css_suffix, color), value, x_position in zip(ALERT_SEVERITY_GROUPS, values, bar_positions):
        bar_height = maximum_bar_height * value / maximum_value
        y_position = baseline - bar_height
        svg_parts.extend(
            [
                f'<rect x="{x_position}" y="{y_position:.1f}" width="{bar_width}" height="{bar_height:.1f}" '
                f'rx="8" fill="{color}"><title>{label} : {value} alerte(s)</title></rect>',
                f'<text x="{x_position + bar_width / 2}" y="{baseline + 22}" text-anchor="middle" '
                f'class="alert-chart-label">{label}</text>',
                f'<text x="{x_position + bar_width / 2}" y="{max(y_position - 8, 14):.1f}" text-anchor="middle" '
                f'class="alert-chart-value">{value}</text>',
            ]
        )

    svg_parts.append("</svg>")
    return Markup("".join(svg_parts))


def _build_alert_donut_chart_svg(alert_counts: AlertSeverityCounts) -> Markup:
    svg_parts = [
        f'<svg class="alert-donut-chart" viewBox="0 0 {DONUT_CHART_SIZE} {DONUT_CHART_SIZE}" role="img" '
        'aria-label="Diagramme circulaire des alertes par niveau de sévérité">',
        f'<circle cx="{DONUT_CENTER}" cy="{DONUT_CENTER}" r="{DONUT_RADIUS}" fill="none" '
        'stroke="#f1e4e9" stroke-width="24" />',
    ]
    offset = 0.0
    if alert_counts.total:
        for (_, _, color), value in zip(
            ALERT_SEVERITY_GROUPS, (alert_counts.critical, alert_counts.medium, alert_counts.low)
        ):
            if not value:
                continue
            segment_length = DONUT_CIRCUMFERENCE * value / alert_counts.total
            remaining_length = DONUT_CIRCUMFERENCE - segment_length
            svg_parts.append(
                f'<circle cx="{DONUT_CENTER}" cy="{DONUT_CENTER}" r="{DONUT_RADIUS}" fill="none" '
                f'stroke="{color}" stroke-width="24" stroke-dasharray="{segment_length:.2f} '
                f'{remaining_length:.2f}" stroke-dashoffset="{-offset:.2f}" '
                f'transform="rotate(-90 {DONUT_CENTER} {DONUT_CENTER})" />'
            )
            offset += segment_length

    svg_parts.extend(
        [
            f'<text x="{DONUT_CENTER}" y="{DONUT_CENTER - 2}" text-anchor="middle" '
            'class="alert-donut-total">',
            f"{alert_counts.total}</text>",
            f'<text x="{DONUT_CENTER}" y="{DONUT_CENTER + 17}" text-anchor="middle" '
            'class="alert-donut-caption">alertes</text>',
            "</svg>",
        ]
    )
    return Markup("".join(svg_parts))
