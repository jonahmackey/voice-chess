import re

def describe_san_first_person(move: str, side: str | None = None) -> str:
    """
    Convert a SAN chess move into a first-person, *future-tense* natural description.

    Args:
        move: SAN string like "Nf3", "exd5", "O-O", "O-O-O", "Qxe5+",
              "e8=Q#", "exd6 e.p.", "Nbd2", "R1e2", "axb8=Q+".
        side: Optional "white" or "black" to name the king's landing square on castling.

    Returns:
        A sentence like "I will move my knight to f3." or
        "I will capture on d5 with my pawn from the e-file."
    """
    original = move.strip()

    piece_names = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop", "N": "knight"}
    ordinals = {"1": "first", "2": "second", "3": "third", "4": "fourth",
                "5": "fifth", "6": "sixth", "7": "seventh", "8": "eighth"}

    def article(name: str) -> str:
        return f"a {name}"

    def side_square(file_letter: str, side_: str | None) -> str | None:
        if side_ is None:
            return None
        side_ = side_.lower()
        if side_ in ("white", "w"):
            return f"{file_letter}1"
        if side_ in ("black", "b"):
            return f"{file_letter}8"
        return None

    def add_check_suffix(desc: str, chk: str | None) -> str:
        if chk == "mate":
            return desc + ", checkmate."
        if chk == "double":
            return desc + ", with double check."
        if chk == "check":
            return desc + ", with check."
        return desc + "."

    s = original

    # En passant marker
    ep = bool(re.search(r'\b(e\.?p\.?)\b', s, flags=re.IGNORECASE))
    s = re.sub(r'\s*\b(e\.?p\.?)\b', '', s, flags=re.IGNORECASE).strip()

    # Extract check/mate
    chk = None
    m_chk = re.search(r'(#|\+\+|\+)([!?]*)$', s)
    if m_chk:
        token = m_chk.group(1)
        chk = "mate" if token == "#" else ("double" if token == "++" else "check")
        s = s[:m_chk.start(1)]

    # Strip trailing annotations
    s = re.sub(r'[!?]+$', '', s).strip()

    # Castling
    if re.fullmatch(r'(O|0)-(O|0)(-(O|0))?', s):
        is_queenside = bool(re.search(r'-(O|0)$', s))
        side_word = "queenside" if is_queenside else "kingside"
        file_letter = "c" if is_queenside else "g"
        dest = side_square(file_letter, side)
        if dest:
            desc = f"I will castle {side_word} to {dest}"
        else:
            desc = f"I will castle {side_word}"
        return add_check_suffix(desc, chk)

    # General SAN parsing
    pattern = re.compile(
        r'^(?P<piece>[KQRBN])?'                # Optional piece (pawn if absent)
        r'(?P<disambig>[a-h1-8]{0,2})'         # Optional disambiguation
        r'(?P<capture>x)?'                     # Optional capture
        r'(?P<dest>[a-h][1-8])'                # Destination
        r'(?:=(?P<promo1>[QRBN])|(?P<promo2>[QRBN]))?'  # Optional promotion
        r'$'
    )
    m = pattern.match(s)
    if not m:
        m2 = re.search(r'([a-h][1-8])', s)
        if m2:
            dest = m2.group(1)
            return f"I will make a move that will land on {dest}."
        return f"I will not be able to parse the move “{original}”."

    piece = m.group("piece") or "P"  # Pawn if no letter
    disambig = m.group("disambig") or ""
    capture = bool(m.group("capture"))
    dest = m.group("dest")
    promo = m.group("promo1") or m.group("promo2")

    piece_name = piece_names.get(piece, "pawn") if piece != "P" else "pawn"

    # Disambiguation phrase after the piece mention
    from_phrase = ""
    if disambig:
        if len(disambig) == 1:
            if 'a' <= disambig <= 'h':
                from_phrase = f" from the {disambig}-file"
            else:
                from_phrase = f" from the {ordinals.get(disambig, disambig)} rank"
        elif len(disambig) == 2 and ('a' <= disambig[0] <= 'h') and ('1' <= disambig[1] <= '8'):
            from_phrase = f" from {disambig}"

    # Pawn captures like 'exd5' imply the origin file
    if piece == "P" and capture and (len(disambig) == 1 and 'a' <= disambig <= 'h'):
        from_phrase = f" from the {disambig}-file"

    # Build the sentence core (future tense)
    if capture:
        if ep and piece == "P":
            base = f"I will capture en passant on {dest} with my pawn{from_phrase}"
        else:
            base = f"I will capture on {dest} with my {piece_name}{from_phrase}"
    else:
        if piece == "P":
            base = f"I will advance my pawn{from_phrase} to {dest}"
        else:
            base = f"I will move my {piece_name}{from_phrase} to {dest}"

    # Promotion (future tense explicitly)
    if promo:
        promo_name = piece_names[promo]
        base += f", and I will promote to {article(promo_name)}"

    return add_check_suffix(base, chk)