"""
MuseXR — Navigation Routes
Direct (from_id, to_id) lookup table for walking directions between Louvre exhibits.
No FAISS, no LLM — pure dictionary lookup.

Exhibit IDs match the 'id' field in exhibits_data.py.
"""

# Human-readable names keyed by exhibit ID
EXHIBIT_NAMES = {
    "winged_victory_of_samothrace": "Winged Victory of Samothrace",
    "venus_de_milo":                "Venus de Milo",
    "cupid_and_psyche":             "Cupid and Psyche",
    "borghese_gladiator":           "The Borghese Gladiator",
    "the_dying_slave":              "The Dying Slave",
    "the_crouching_scribe":         "The Seated Scribe",
    "bastet_cat_statue":            "Bastet Cat Statue",
    "la_siesta_foyatier":           "La Siesta",
}

ROUTES: dict[tuple[str, str], str] = {

    # ── From Winged Victory (Room 703, Denon, Level 1) ───────────────────────
    ("winged_victory_of_samothrace", "venus_de_milo"): (
        "Descend the Daru Staircase to Level 0. "
        "Follow signs for Greek Antiquities into the Sully wing — "
        "Venus de Milo is at the end of the Galerie des Antiques corridor (Room 345), about 5 minutes."
    ),
    ("winged_victory_of_samothrace", "cupid_and_psyche"): (
        "Descend the Daru Staircase to Level 0. "
        "Room 403 (the Michelangelo Gallery) is a 3-minute walk south in the Denon wing."
    ),
    ("winged_victory_of_samothrace", "the_dying_slave"): (
        "Descend the Daru Staircase to Level 0. "
        "Room 403 (the Michelangelo Gallery) is a 3-minute walk south in the Denon wing — "
        "the Dying Slave is here alongside Cupid and Psyche."
    ),
    ("winged_victory_of_samothrace", "borghese_gladiator"): (
        "Descend the Daru Staircase to Level 0. "
        "Cross into the Sully wing and follow signs for Greek Antiquities — "
        "Room 348 is about 6 minutes from the bottom of the staircase."
    ),
    ("winged_victory_of_samothrace", "the_crouching_scribe"): (
        "Descend the Daru Staircase to Level 0. "
        "Cross into the Sully wing, take the stairs to Level 1, "
        "then follow signs for Egyptian Antiquities to Room 635 — about 8 minutes."
    ),
    ("winged_victory_of_samothrace", "bastet_cat_statue"): (
        "Descend the Daru Staircase to Level 0. "
        "Cross into Sully, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities — "
        "Room 630 is a few rooms before Room 635, about 8 minutes."
    ),
    ("winged_victory_of_samothrace", "la_siesta_foyatier"): (
        "Descend the Daru Staircase to Level 0. "
        "Head north through the Pyramid area and follow signs for the Richelieu wing — "
        "Room 225 is on Level 0 in the Modern Sculpture galleries, about 10 minutes."
    ),

    # ── From Venus de Milo (Room 345, Sully, Level 0) ────────────────────────
    ("venus_de_milo", "winged_victory_of_samothrace"): (
        "Head east through the Greek Antiquities corridor into the Denon wing, "
        "then climb the Daru Staircase to Level 1 (Room 703) — about 5 minutes."
    ),
    ("venus_de_milo", "cupid_and_psyche"): (
        "Head east through the Greek Antiquities corridor into the Denon wing. "
        "Room 403 (the Michelangelo Gallery) is on Level 0 — about 5 minutes."
    ),
    ("venus_de_milo", "the_dying_slave"): (
        "Head east through the Greek Antiquities corridor into the Denon wing. "
        "Room 403 (the Michelangelo Gallery) is on Level 0 — "
        "the Dying Slave is here alongside Cupid and Psyche, about 5 minutes."
    ),
    ("venus_de_milo", "borghese_gladiator"): (
        "Room 348 is just a few rooms along the same Level 0 Sully corridor — a 2-minute walk."
    ),
    ("venus_de_milo", "the_crouching_scribe"): (
        "Head north through the Sully wing and take the stairs to Level 1. "
        "Follow signs for Egyptian Antiquities to Room 635 — about 8 minutes."
    ),
    ("venus_de_milo", "bastet_cat_statue"): (
        "Head north through the Sully wing, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities — "
        "Room 630 is a few rooms before Room 635, about 8 minutes."
    ),
    ("venus_de_milo", "la_siesta_foyatier"): (
        "Head north through Sully toward the Pyramid, "
        "then cross into the Richelieu wing — "
        "Room 225 is on Level 0 in the Modern Sculpture galleries, about 8 minutes."
    ),

    # ── From Cupid and Psyche (Room 403, Denon, Level 0) ─────────────────────
    ("cupid_and_psyche", "winged_victory_of_samothrace"): (
        "Head north toward the Daru Staircase and climb to Level 1 (Room 703) — about 5 minutes."
    ),
    ("cupid_and_psyche", "venus_de_milo"): (
        "Head west from Room 403 into the Sully wing, "
        "following signs for Greek Antiquities on Level 0 (Room 345) — about 5 minutes."
    ),
    ("cupid_and_psyche", "the_dying_slave"): (
        "Both are displayed in the same room — Room 403, Denon wing, Level 0."
    ),
    ("cupid_and_psyche", "borghese_gladiator"): (
        "Head west from Room 403 into the Sully wing — "
        "Room 348 is in the Greek Antiquities corridor on Level 0, about 4 minutes."
    ),
    ("cupid_and_psyche", "the_crouching_scribe"): (
        "Head west into the Sully wing, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities to Room 635 — about 10 minutes."
    ),
    ("cupid_and_psyche", "bastet_cat_statue"): (
        "Head west into Sully, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities — "
        "Room 630 is a few rooms before Room 635, about 10 minutes."
    ),
    ("cupid_and_psyche", "la_siesta_foyatier"): (
        "Head north from Room 403 toward the Pyramid, "
        "then cross into the Richelieu wing — "
        "Room 225 is on Level 0 in the Modern Sculpture galleries, about 8 minutes."
    ),

    # ── From The Borghese Gladiator (Room 348, Sully, Level 0) ───────────────
    ("borghese_gladiator", "winged_victory_of_samothrace"): (
        "Head east into the Denon wing, "
        "then climb the Daru Staircase to Level 1 (Room 703) — about 8 minutes."
    ),
    ("borghese_gladiator", "venus_de_milo"): (
        "Room 345 is just a few rooms along the same Level 0 Sully corridor — a 2-minute walk."
    ),
    ("borghese_gladiator", "cupid_and_psyche"): (
        "Head east into the Denon wing ground floor — "
        "Room 403 (the Michelangelo Gallery) is about 5 minutes."
    ),
    ("borghese_gladiator", "the_dying_slave"): (
        "Head east into the Denon wing ground floor — "
        "Room 403 (the Michelangelo Gallery) is about 5 minutes. "
        "The Dying Slave is here alongside Cupid and Psyche."
    ),
    ("borghese_gladiator", "the_crouching_scribe"): (
        "Head north through the Sully wing and take the stairs to Level 1, "
        "then follow signs for Egyptian Antiquities to Room 635 — about 8 minutes."
    ),
    ("borghese_gladiator", "bastet_cat_statue"): (
        "Head north through Sully, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities — "
        "Room 630 is a few rooms before Room 635, about 8 minutes."
    ),
    ("borghese_gladiator", "la_siesta_foyatier"): (
        "Head north through Sully toward the Pyramid, "
        "then cross into the Richelieu wing — "
        "Room 225 is on Level 0 in the Modern Sculpture galleries, about 8 minutes."
    ),

    # ── From The Dying Slave (Room 403, Denon, Level 0) ──────────────────────
    ("the_dying_slave", "winged_victory_of_samothrace"): (
        "Head north toward the Daru Staircase and climb to Level 1 (Room 703) — about 5 minutes."
    ),
    ("the_dying_slave", "venus_de_milo"): (
        "Head west from Room 403 into the Sully wing, "
        "following signs for Greek Antiquities on Level 0 (Room 345) — about 5 minutes."
    ),
    ("the_dying_slave", "cupid_and_psyche"): (
        "Both are displayed in the same room — Room 403, Denon wing, Level 0."
    ),
    ("the_dying_slave", "borghese_gladiator"): (
        "Head west from Room 403 into the Sully wing — "
        "Room 348 is in the Greek Antiquities corridor on Level 0, about 4 minutes."
    ),
    ("the_dying_slave", "the_crouching_scribe"): (
        "Head west into the Sully wing, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities to Room 635 — about 10 minutes."
    ),
    ("the_dying_slave", "bastet_cat_statue"): (
        "Head west into Sully, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities — "
        "Room 630 is a few rooms before Room 635, about 10 minutes."
    ),
    ("the_dying_slave", "la_siesta_foyatier"): (
        "Head north from Room 403 toward the Pyramid, "
        "then cross into the Richelieu wing — "
        "Room 225 is on Level 0 in the Modern Sculpture galleries, about 8 minutes."
    ),

    # ── From The Seated Scribe (Room 635, Sully, Level 1) ────────────────────
    ("the_crouching_scribe", "winged_victory_of_samothrace"): (
        "Descend to Level 0, cross east into the Denon wing, "
        "then climb the Daru Staircase to Level 1 (Room 703) — about 10 minutes."
    ),
    ("the_crouching_scribe", "venus_de_milo"): (
        "Descend to Level 0 and head south through the Sully wing "
        "toward Greek Antiquities (Room 345) — about 8 minutes."
    ),
    ("the_crouching_scribe", "cupid_and_psyche"): (
        "Descend to Level 0, cross east into the Denon wing — "
        "Room 403 (the Michelangelo Gallery) is about 10 minutes."
    ),
    ("the_crouching_scribe", "the_dying_slave"): (
        "Descend to Level 0, cross east into the Denon wing — "
        "Room 403 (the Michelangelo Gallery) is about 10 minutes. "
        "The Dying Slave is here alongside Cupid and Psyche."
    ),
    ("the_crouching_scribe", "borghese_gladiator"): (
        "Descend to Level 0, head south through the Sully wing "
        "toward Greek Antiquities — Room 348 is about 8 minutes."
    ),
    ("the_crouching_scribe", "bastet_cat_statue"): (
        "Room 630 is just a few rooms south in the same Egyptian Antiquities corridor — a 2-minute walk."
    ),
    ("the_crouching_scribe", "la_siesta_foyatier"): (
        "Descend to Level 0, head north/west through Sully toward the Pyramid, "
        "then cross into the Richelieu wing — "
        "Room 225 is on Level 0 in the Modern Sculpture galleries, about 10 minutes."
    ),

    # ── From Bastet Cat Statue (Room 630, Sully, Level 1) ────────────────────
    ("bastet_cat_statue", "winged_victory_of_samothrace"): (
        "Descend to Level 0, cross east into the Denon wing, "
        "then climb the Daru Staircase to Level 1 (Room 703) — about 10 minutes."
    ),
    ("bastet_cat_statue", "venus_de_milo"): (
        "Descend to Level 0 and head south through Sully "
        "toward Greek Antiquities (Room 345) — about 8 minutes."
    ),
    ("bastet_cat_statue", "cupid_and_psyche"): (
        "Descend to Level 0, cross east into the Denon wing — "
        "Room 403 (the Michelangelo Gallery) is about 10 minutes."
    ),
    ("bastet_cat_statue", "the_dying_slave"): (
        "Descend to Level 0, cross east into the Denon wing — "
        "Room 403 is about 10 minutes. "
        "The Dying Slave is here alongside Cupid and Psyche."
    ),
    ("bastet_cat_statue", "borghese_gladiator"): (
        "Descend to Level 0, head south through Sully "
        "toward Greek Antiquities — Room 348 is about 8 minutes."
    ),
    ("bastet_cat_statue", "the_crouching_scribe"): (
        "Room 635 is just a few rooms north in the same Egyptian Antiquities corridor — a 2-minute walk."
    ),
    ("bastet_cat_statue", "la_siesta_foyatier"): (
        "Descend to Level 0, head north/west through Sully toward the Pyramid, "
        "then cross into the Richelieu wing — "
        "Room 225 is on Level 0 in the Modern Sculpture galleries, about 10 minutes."
    ),

    # ── From La Siesta (Room 225, Richelieu, Level 0) ────────────────────────
    ("la_siesta_foyatier", "winged_victory_of_samothrace"): (
        "Head east from Richelieu into the Denon wing, "
        "then climb the Daru Staircase to Level 1 (Room 703) — about 10 minutes."
    ),
    ("la_siesta_foyatier", "venus_de_milo"): (
        "Head south/east from Richelieu, cross the Pyramid area into the Sully wing, "
        "follow signs for Greek Antiquities on Level 0 (Room 345) — about 8 minutes."
    ),
    ("la_siesta_foyatier", "cupid_and_psyche"): (
        "Head east from Richelieu, cross the Pyramid area into the Denon wing Level 0 — "
        "Room 403 (the Michelangelo Gallery) is about 8 minutes."
    ),
    ("la_siesta_foyatier", "the_dying_slave"): (
        "Head east from Richelieu, cross the Pyramid area into the Denon wing Level 0 — "
        "Room 403 is about 8 minutes. The Dying Slave is here alongside Cupid and Psyche."
    ),
    ("la_siesta_foyatier", "borghese_gladiator"): (
        "Head south/east from Richelieu into the Sully wing, "
        "follow signs for Greek Antiquities on Level 0 (Room 348) — about 8 minutes."
    ),
    ("la_siesta_foyatier", "the_crouching_scribe"): (
        "Head east into Sully, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities to Room 635 — about 10 minutes."
    ),
    ("la_siesta_foyatier", "bastet_cat_statue"): (
        "Head east into Sully, take the stairs to Level 1, "
        "follow signs for Egyptian Antiquities — "
        "Room 630 is a few rooms before Room 635, about 10 minutes."
    ),
}
