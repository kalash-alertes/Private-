"""Graphique « Activité des alertes » du tableau de bord, dessiné en SVG côté serveur (remplace recharts de la maquette).

Deux aires superposées : alertes détectées (bleu) et incidents traités (turquoise), une valeur par jour.
Les couleurs reprennent celles de la maquette. Le SVG s'adapte à la largeur du panneau (`width="100%"`).
"""

from dataclasses import dataclass
from datetime import date
from html import escape

from markupsafe import Markup

from web_interface.display_formatting import format_short_day_label

CHART_WIDTH = 640
CHART_HEIGHT = 205
LEFT_MARGIN = 34  # place des graduations de l'axe vertical
RIGHT_MARGIN = 10
TOP_MARGIN = 10
BOTTOM_MARGIN = 26  # place des étiquettes de jours
HORIZONTAL_GRID_LINE_COUNT = 4

DETECTED_ALERTS_COLOR = "#6d9cff"
HANDLED_INCIDENTS_COLOR = "#35c6ad"


@dataclass(frozen=True)
class ActivityChartPoint:
    day: date
    detected_alert_count: int
    handled_incident_count: int


def build_activity_chart_svg(points: list[ActivityChartPoint]) -> Markup:
    """Retourne le SVG du graphique. Avec moins de deux jours, il n'y a pas de courbe à tracer : SVG vide."""
    if len(points) < 2:
        return Markup("")
    plot_width = CHART_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    plot_height = CHART_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN
    plot_bottom = TOP_MARGIN + plot_height
    highest_value = max(max(point.detected_alert_count, point.handled_incident_count) for point in points)
    vertical_scale_maximum = _round_up_to_readable_maximum(highest_value)

    def x_position(point_index: int) -> float:
        return LEFT_MARGIN + plot_width * point_index / (len(points) - 1)

    def y_position(value: int) -> float:
        return plot_bottom - plot_height * value / vertical_scale_maximum

    svg_parts = [
        f'<svg class="activity-chart" viewBox="0 0 {CHART_WIDTH} {CHART_HEIGHT}" width="100%" role="img" '
        f'aria-label="Alertes détectées et incidents traités par jour">',
        "<defs>",
        _build_vertical_fade_gradient("detected-alerts-fill", DETECTED_ALERTS_COLOR, 0.22),
        _build_vertical_fade_gradient("handled-incidents-fill", HANDLED_INCIDENTS_COLOR, 0.16),
        "</defs>",
    ]
    for grid_line_index in range(HORIZONTAL_GRID_LINE_COUNT + 1):
        grid_value = vertical_scale_maximum * grid_line_index / HORIZONTAL_GRID_LINE_COUNT
        grid_y = y_position(grid_value)
        svg_parts.append(
            f'<line x1="{LEFT_MARGIN}" x2="{CHART_WIDTH - RIGHT_MARGIN}" y1="{grid_y:.1f}" y2="{grid_y:.1f}" '
            f'stroke="#263245" stroke-dasharray="3 5" />'
            f'<text x="{LEFT_MARGIN - 8}" y="{grid_y + 3:.1f}" text-anchor="end" class="chart-axis-label">'
            f"{grid_value:g}</text>"
        )
    for point_index, point in enumerate(points):
        svg_parts.append(
            f'<text x="{x_position(point_index):.1f}" y="{CHART_HEIGHT - 6}" text-anchor="middle" '
            f'class="chart-axis-label">{escape(format_short_day_label(point.day))}</text>'
        )
    for series_values, line_color, fill_identifier, series_name in [
        ([point.detected_alert_count for point in points], DETECTED_ALERTS_COLOR, "detected-alerts-fill", "Détectées"),
        ([point.handled_incident_count for point in points], HANDLED_INCIDENTS_COLOR, "handled-incidents-fill", "Traités"),
    ]:
        line_coordinates = " ".join(
            f"{x_position(index):.1f},{y_position(value):.1f}" for index, value in enumerate(series_values)
        )
        area_coordinates = (
            f"{x_position(0):.1f},{plot_bottom} {line_coordinates} {x_position(len(points) - 1):.1f},{plot_bottom}"
        )
        svg_parts.append(f'<polygon points="{area_coordinates}" fill="url(#{fill_identifier})" />')
        svg_parts.append(
            f'<polyline points="{line_coordinates}" fill="none" stroke="{line_color}" stroke-width="2.5" '
            f'stroke-linejoin="round" stroke-linecap="round" />'
        )
        # Une info-bulle native (<title>) par point : pas besoin de JavaScript pour lire les valeurs.
        for index, value in enumerate(series_values):
            svg_parts.append(
                f'<circle cx="{x_position(index):.1f}" cy="{y_position(value):.1f}" r="3.5" fill="{line_color}">'
                f"<title>{escape(format_short_day_label(points[index].day))} — {series_name} : {value}</title></circle>"
            )
    svg_parts.append("</svg>")
    return Markup("".join(svg_parts))


def _round_up_to_readable_maximum(highest_value: int) -> int:
    """Borne haute de l'axe : multiple de 4 (graduations entières), au minimum 4 pour un graphique vide lisible."""
    return max(4, -(-highest_value // HORIZONTAL_GRID_LINE_COUNT) * HORIZONTAL_GRID_LINE_COUNT)


def _build_vertical_fade_gradient(gradient_identifier: str, color: str, top_opacity: float) -> str:
    return (
        f'<linearGradient id="{gradient_identifier}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="{top_opacity}" />'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0" /></linearGradient>'
    )
