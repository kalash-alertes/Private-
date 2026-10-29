"""Rendu des icônes SVG en ligne dans les gabarits : `{{ icon("shield_alert", 18) }}`.

Les formes viennent de `icon_shapes.py` (généré depuis la maquette) ; quelques icônes absentes de la maquette sont
déclarées ici. Le rendu est fait côté serveur : aucune bibliothèque JavaScript d'icônes n'est nécessaire.
"""

from html import escape

from markupsafe import Markup

from web_interface.icon_shapes import ICON_SHAPES_BY_NAME

# Icônes du jeu lucide (licence ISC) non utilisées par la maquette, nécessaires à cette interface.
ADDITIONAL_ICON_SHAPES_BY_NAME: dict[str, list[tuple[str, dict[str, str]]]] = {
    "settings": [
        (
            "path",
            {
                "d": "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73"
                "l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73"
                "l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44"
                "a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39"
                "a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73"
                "l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"
            },
        ),
        ("circle", {"cx": "12", "cy": "12", "r": "3"}),
    ],
    "arrow_left": [("path", {"d": "m12 19-7-7 7-7"}), ("path", {"d": "M19 12H5"})],
}

ALL_ICON_SHAPES_BY_NAME = {**ICON_SHAPES_BY_NAME, **ADDITIONAL_ICON_SHAPES_BY_NAME}


def render_icon(icon_name: str, size: int = 16, stroke_width: float = 2, css_class: str = "") -> Markup:
    """Retourne le SVG de l'icône. Lève KeyError si l'icône est inconnue (erreur de gabarit à corriger)."""
    shape_elements = "".join(
        f"<{tag} " + " ".join(f'{name}="{escape(value)}"' for name, value in attributes.items()) + " />"
        for tag, attributes in ALL_ICON_SHAPES_BY_NAME[icon_name]
    )
    class_attribute = f' class="{escape(css_class)}"' if css_class else ""
    return Markup(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true"{class_attribute}>{shape_elements}</svg>'
    )
