"""
Museum knowledge base — Louvre Museum & Tuileries Garden, Paris
Eight iconic sculptures spanning antiquity to the 20th century.

Each exhibit contains structured sections so the RAG engine can answer
questions from multiple angles (facts, visual, historical, technique, story).
"""

EXHIBITS = [
    {
        "id": "winged_victory_of_samothrace",
        "name": "Winged Victory of Samothrace",
        "artist": "Unknown (Rhodian school)",
        "year": "c. 190 BC",
        "type": "sculpture",
        "period": "Hellenistic Greece, c. 190 BC",
        "location": "Louvre, Salle 703 (top of the Daru Staircase)",
        "key_facts": (
            "Marble, height 244 cm (96 in). "
            "Created c. 190 BC, likely to commemorate a naval victory. "
            "Discovered in fragments on the island of Samothrace in 1863 by Charles Champoiseau. "
            "The head and arms have never been found. "
            "Displayed at the top of the Daru Staircase in the Louvre — one of the most visited works in the world."
        ),
        "visual_description": (
            "A colossal winged female figure — the goddess Nike — stands on the prow of a stone ship, "
            "her enormous wings spread wide behind her as if she has just alighted from the sky. "
            "She leans slightly forward, her drapery clinging to her body as if buffeted by sea wind, "
            "revealing the contours beneath in fine detail. "
            "The thin fabric swirls around her legs and billows behind her like a sail. "
            "The head and both arms are missing, yet the figure radiates a sense of triumphant forward motion "
            "that no complete statue could surpass. "
            "The stone ship's prow beneath her feet recalls the sculpture's original setting near the sea."
        ),
        "historical_context": (
            "The statue was created on the Greek island of Rhodes, likely to celebrate a naval victory "
            "— possibly the Battle of Side or Myonessos, fought around 190 BC against the Seleucid fleet. "
            "It was erected at the Sanctuary of the Great Gods on Samothrace, placed in a hillside niche "
            "above a shallow reflecting pool so the ship's prow appeared to sail on water. "
            "Charles Champoiseau, a French diplomat and amateur archaeologist, found it in pieces in 1863 "
            "and shipped the fragments to Paris. "
            "The right hand was found separately in 1950 and is now displayed in a case nearby. "
            "The statue became a symbol of French national cultural ambition after its installation in the Louvre."
        ),
        "technique": (
            "The figure was carved from Parian marble — a fine-grained white marble from the Aegean island of Paros, "
            "prized since antiquity for its translucency and workability. "
            "The ship's prow is carved from a darker grey marble from Rhodes, emphasising the contrast with the figure above. "
            "The drapery technique — known as 'wet drapery' or 'wind-blown drapery' — "
            "involves carving fabric so thin it appears transparent, revealing the body beneath. "
            "This was the supreme technical challenge for Hellenistic sculptors: "
            "suggesting lightness and motion in solid stone. "
            "The drill was used extensively to cut deep shadows in the folds, "
            "creating a dramatic play of light and dark across the surface."
        ),
        "story": (
            "The Winged Victory was evacuated from the Louvre at the start of both World Wars — "
            "a remarkable logistical feat given her size — and stored in châteaux in the French countryside. "
            "In 1939, as German forces advanced, she was wrapped and transported on a specially built stretcher "
            "to Château de Valençay in the Loire Valley. "
            "She returned to the Louvre after liberation in 1945. "
            "A major restoration between 2012 and 2014 cleaned the statue and reinforced the base, "
            "revealing for the first time traces of red and pink pigment — "
            "the marble was never pure white, but richly painted. "
            "Auguste Rodin called her 'the most beautiful work the ancient world has left us.'"
        ),
        "content": (
            "The Winged Victory of Samothrace is a Hellenistic marble sculpture created around 190 BC, "
            "likely to celebrate a Greek naval victory. Standing 244 cm tall, the goddess Nike descends onto "
            "the prow of a stone ship, her wings spread and her drapery whipped by sea wind in a supreme "
            "display of Hellenistic technical mastery. Discovered in fragments on the island of Samothrace "
            "in 1863, she has stood at the top of the Louvre's Daru Staircase ever since — "
            "headless, armless, and completely unforgettable. "
            "Rodin called her 'the most beautiful work the ancient world has left us.'"
        ),
        "shop": (
            "The Louvre boutique sells hand-patinated resin replicas of the Winged Victory in three sizes: "
            "18 cm, 34 cm, and 50 cm — each cast from a mould taken directly from the original marble. "
            "Also available: art prints from €22, a Monnaie de Paris souvenir medal, and a chalcography engraving. "
            "Browse the full collection at boutique.louvre.fr/en/products/400628-the-winged-victory-of-samothrace/"
        ),
    },
    {
        "id": "venus_de_milo",
        "name": "Venus de Milo",
        "artist": "Attributed to Alexandros of Antioch",
        "year": "c. 130–100 BC",
        "type": "sculpture",
        "period": "Hellenistic Greece, c. 130–100 BC",
        "location": "Louvre, Salle 345 (Galerie de Milo)",
        "key_facts": (
            "Marble, height 203 cm (80 in). "
            "Created c. 130–100 BC, attributed to Alexandros of Antioch based on an inscription found nearby. "
            "Discovered in 1820 by a farmer on the Greek island of Milos. "
            "Arms missing since discovery — their original position has never been agreed upon. "
            "Acquired by France and presented to Louis XVIII, then donated to the Louvre."
        ),
        "visual_description": (
            "A life-size female figure stands in a gentle S-curve — the classical contrapposto pose — "
            "her weight resting on her right leg while the left steps slightly forward. "
            "She is nude from the waist up; a heavy marble drapery wraps her hips and pools at her feet. "
            "Both arms are missing from just above the elbow. "
            "Her face has a serene, idealised beauty: wide-set eyes, a straight nose, and full lips "
            "with the faintest suggestion of a smile. "
            "Her hair is pulled back with a few loose strands framing her face. "
            "The marble surface has a warm, creamy tone, with the faintest traces of ancient pigment "
            "still visible in the carved hair."
        ),
        "historical_context": (
            "The statue was found on 8 April 1820 by a peasant farmer named Yorgos Kentrotas "
            "while digging in his field on the island of Milos. "
            "A French naval officer, Olivier Voutier, was present at the discovery and recognised its value. "
            "France purchased it from the Ottoman authorities who controlled the island at the time "
            "and presented it to King Louis XVIII, who donated it to the Louvre in 1821. "
            "The statue arrived in Paris as the Louvre was still recovering from the upheavals of the Napoleonic era, "
            "and was immediately promoted as a replacement for classical works France had lost. "
            "Her identity as Aphrodite (Venus) is widely accepted but not certain — "
            "she may represent a sea goddess or the personification of victory."
        ),
        "technique": (
            "The Venus de Milo is carved from two blocks of Parian marble joined at the hips — "
            "a join line is visible under close inspection. "
            "This two-part construction was common in large-scale Hellenistic sculpture "
            "and allowed sculptors to work on each section separately before assembly. "
            "The contrapposto pose — weight on one leg, hips and shoulders tilted in opposite directions — "
            "creates a natural, relaxed asymmetry that classical Greek artists developed "
            "to move beyond the rigid frontality of archaic sculpture. "
            "The drapery is carved with particular virtuosity: the fabric appears heavy and real, "
            "clinging to the thighs and threatening to fall. "
            "Originally the surface was painted, and metal accessories — "
            "earrings, a bracelet, a headband — were attached via small drilled holes still visible today."
        ),
        "story": (
            "The debate over the missing arms has fascinated scholars for two centuries. "
            "Theories include: she held a shield reflecting her own image, "
            "she held an apple (the prize awarded by Paris of Troy), "
            "she was part of a group with a male figure (perhaps Ares or Poseidon), "
            "or she simply held drapery that was slipping off her hips. "
            "No reconstruction has been universally accepted. "
            "When the statue arrived in Paris, a Greek inscription identifying the artist as Alexandros of Antioch "
            "was found on the base — but French authorities deliberately suppressed it, "
            "preferring the statue to be seen as a great classical (5th-century BC) masterpiece "
            "rather than a later Hellenistic work. "
            "The plinth with the inscription was conveniently 'lost' and only rediscovered much later."
        ),
        "content": (
            "The Venus de Milo is a marble sculpture created c. 130–100 BC, attributed to Alexandros of Antioch, "
            "and standing 203 cm tall. Discovered in 1820 on the Greek island of Milos, she depicts Aphrodite "
            "in a gentle contrapposto pose, nude from the waist up with draped fabric pooling at her feet. "
            "Both arms have been missing since her discovery, and their original position remains the subject "
            "of scholarly debate. France acquired her in 1821 and she has been a centrepiece of the Louvre ever since, "
            "becoming one of the most recognised works of art in human history."
        ),
        "shop": (
            "The Louvre boutique offers an extensive Venus de Milo collection. "
            "Resin replicas hand-patinated from the original mould are available in 16 cm, 30 cm, and 50 cm. "
            "A bronze cast (32 × 9.5 × 8 cm) is also available. "
            "For something more playful, the Pop Art versions in light blue or orange make striking decorative pieces. "
            "Additional products include an art print (24 × 30 cm), a magnet, and an illustrated monograph (120 pages, 118 illustrations). "
            "Browse the full collection at boutique.louvre.fr/en/products/400626-the-venus-de-milo/"
        ),
    },
    {
        "id": "cupid_and_psyche",
        "name": "Cupid and Psyche",
        "artist": "Antonio Canova",
        "year": "1793",
        "type": "sculpture",
        "period": "Neoclassicism, 1793",
        "location": "Louvre, Salle 403 (Denon Wing — Michelangelo Gallery)",
        "key_facts": (
            "Marble, height 155 cm (61 in). "
            "Carved 1787–93 by Antonio Canova. "
            "Commissioned by Colonel John Campbell (later Lord Cawdor) in 1787. "
            "Purchased by Joachim Murat, Napoleon's brother-in-law, and entered the Louvre in 1824. "
            "A second version (1794) is in the Hermitage Museum, St. Petersburg."
        ),
        "visual_description": (
            "Cupid descends from above, his great wings spread wide, his young body twisting dynamically "
            "as he leans down toward the reclining Psyche. "
            "His arms wrap around her as she arches upward to receive his kiss, her arms raised "
            "to cradle his head — the two faces almost touching, lips barely apart. "
            "Psyche reclines on a rocky base, her drapery falling away, her body languid but alive with anticipation. "
            "The composition is a spiral: viewed from any angle, new lines of tension and tenderness are revealed. "
            "The marble surface is polished to an almost translucent smoothness, suggesting living flesh. "
            "The fingertips barely graze skin, and the space between their lips — "
            "the moment before the kiss — is the emotional heart of the work."
        ),
        "historical_context": (
            "The subject comes from The Golden Ass, a 2nd-century Latin novel by Apuleius. "
            "In the story, Psyche — a mortal girl of extraordinary beauty — is condemned by jealous Venus "
            "to fall into an eternal sleep. Cupid, who loves her, revives her with a kiss. "
            "The myth was a favourite of Neoclassical artists because it combined classical subject matter "
            "with intense emotional content. "
            "Canova began the work in Rome in 1787 on a commission from a British collector. "
            "It passed through several hands before being purchased by Joachim Murat — "
            "King of Naples and Napoleon's brother-in-law — and eventually entered the Louvre's collection. "
            "Napoleon himself admired Canova enormously and commissioned several works from him, "
            "though Canova maintained a studied political neutrality throughout the imperial period."
        ),
        "technique": (
            "Canova worked in white Carrara marble, which he chose for its fine grain and brilliant surface. "
            "His studio practice involved assistants roughing out the form from a plaster model, "
            "but Canova himself completed all the final surfaces. "
            "His signature technique was extreme surface polish — he used pumice and increasingly fine abrasives "
            "to bring the marble to a near-translucent glow, mimicking the softness of real skin. "
            "The spiral composition is a deliberate tour de force: "
            "Baroque sculptures such as Bernini's had used spiralling forms to generate energy, "
            "but Canova's spiral generates tenderness rather than drama. "
            "The open wings required careful structural engineering — their weight is distributed "
            "through hidden iron armatures embedded in the marble."
        ),
        "story": (
            "Canova originally included a tiny butterfly — the Greek symbol of the soul, psyche — "
            "resting near Psyche's hand, a detail easily missed by visitors. "
            "When Napoleon occupied Rome in 1796, he took a personal interest in Canova and urged the sculptor "
            "to create a monument to French glory. Canova deflected politely and continued his own work. "
            "After Napoleon's fall, Canova was sent to Paris by the Pope as a diplomat "
            "to negotiate the return of artworks seized by Napoleon — "
            "he recovered hundreds of pieces for Italy, though not all were returned. "
            "The Cupid and Psyche in the Louvre stayed in Paris, having been legitimately purchased "
            "rather than seized. The St. Petersburg version, made for the same composition, "
            "was completed a year later and is considered equally fine."
        ),
        "content": (
            "Cupid and Psyche is a marble sculpture by Antonio Canova, completed in 1793. "
            "It depicts the moment from Apuleius's myth when Cupid revives the sleeping Psyche with a kiss — "
            "the god of love descending with spread wings, their faces almost touching, "
            "arms entwined in an embrace of extraordinary tenderness. "
            "Carved from white Carrara marble and polished to a skin-like smoothness, "
            "the spiralling composition reveals new emotion from every angle. "
            "It entered the Louvre in 1824 and is considered the supreme masterpiece of Neoclassical sculpture."
        ),
        "shop": (
            "The Louvre boutique sells a hand-patinated resin replica of Psyche Revived by Cupid's Kiss "
            "(31 × 22 × 33 cm, €1,380) — one of the most prestigious pieces in the collection, "
            "cast from a mould taken directly from the original Canova marble. "
            "Also available: an art print (24 × 30 cm) and a decorative poster. "
            "Browse the full collection at boutique.louvre.fr/en/product/14567-psyche-revived-by-cupid-kiss-antonio-canova.html"
        ),
    },
    {
        "id": "borghese_gladiator",
        "name": "The Borghese Gladiator",
        "artist": "Agasias of Ephesus",
        "year": "c. 100 BC",
        "type": "sculpture",
        "period": "Hellenistic Greece, c. 100 BC",
        "location": "Louvre, Salle 348 (Galerie des Antiques)",
        "key_facts": (
            "Marble, height 199 cm (78 in). "
            "Carved c. 100 BC by Agasias of Ephesus — his name is signed on the base. "
            "Part of the Borghese collection, Rome, until 1807 when Napoleon purchased it from his brother-in-law "
            "Camillo Borghese along with 344 other antiquities. "
            "Not actually a gladiator — the figure is an unarmed athlete or warrior in combat stance."
        ),
        "visual_description": (
            "A muscular, naked male figure lunges forward in a dynamic diagonal, "
            "his body twisting as he thrusts his left arm upward and outward. "
            "His right leg is braced behind him, his left leg extended forward, "
            "the entire pose suggesting he is defending against an opponent on horseback — "
            "ducking under a sword or lance while preparing a counter-thrust. "
            "The figure is unarmoured and carries no visible weapon, heightening the sense of raw physical power. "
            "The musculature is rendered with extraordinary anatomical precision: "
            "every tendon, vein, and muscle group is defined. "
            "The face — turned upward and to the right — shows fierce concentration rather than pain."
        ),
        "historical_context": (
            "The statue was created on the Greek island of Delos, a major centre of Hellenistic art and trade. "
            "It was brought to Rome at some point in antiquity and eventually became part of the Borghese collection "
            "at the Villa Borghese in Rome — one of the greatest private art collections in Europe. "
            "In 1807, Napoleon Bonaparte forced his brother-in-law Camillo Borghese to sell "
            "the entire sculpture collection to France for 8 million francs — "
            "a transaction widely regarded as coerced. "
            "The 344 sculptures arrived in Paris and formed the basis of the Louvre's antiquities collection. "
            "The 'gladiator' misidentification dates to the Renaissance, when scholars assumed "
            "any fighting male figure in ancient art must be a gladiator."
        ),
        "technique": (
            "Agasias worked in Pentelic marble — the fine white marble quarried near Athens, "
            "used for the Parthenon. "
            "The extreme torsion of the pose is a Hellenistic innovation: "
            "classical Greek sculpture of the 5th century BC showed figures in frontal or simple profile views, "
            "but Hellenistic artists developed complex multi-axis twists that demanded to be seen in the round. "
            "The outstretched left arm — extending far from the body — was a technical risk: "
            "marble is strong under compression but weak under tension, "
            "and any long unsupported limb can crack under its own weight. "
            "The sculptor solved this by keeping the arm slightly raised, "
            "distributing its weight through the shoulder and torso."
        ),
        "story": (
            "The Borghese Gladiator was one of the most copied and studied sculptures in Europe from the Renaissance onward. "
            "Casts and copies appeared in the studios of every major art academy, "
            "and young artists from Rubens to Jacques-Louis David drew from it obsessively. "
            "When Napoleon seized the collection, it provoked outrage in Rome — "
            "Pope Pius VII protested, and the Italian press mourned the loss of national heritage. "
            "The transaction was never reversed: unlike many Napoleonic acquisitions, "
            "the Borghese marbles were not returned after his defeat "
            "because they had been technically purchased rather than seized in war. "
            "Today the Gladiator remains in the Louvre while the empty niches of Villa Borghese "
            "still bear the marks of its absence."
        ),
        "content": (
            "The Borghese Gladiator is a marble sculpture carved c. 100 BC by Agasias of Ephesus "
            "— one of the few ancient sculptures signed by its creator. "
            "Standing 199 cm tall, it depicts an unarmed male athlete or warrior in a powerful lunging pose, "
            "twisting dramatically to defend against an unseen mounted opponent. "
            "Its extraordinary anatomical detail and dynamic torsion made it one of the most studied "
            "sculptures in European art academies for centuries. "
            "Napoleon coerced its purchase from the Borghese family in 1807, "
            "and it has been in the Louvre ever since."
        ),
        "shop": (
            "The Louvre boutique does not currently offer a dedicated replica of the Borghese Gladiator. "
            "However, art prints of works from the Louvre's Greek Antiquities collection are available from €22, "
            "and the on-site gift shop at the Louvre may stock additional items. "
            "Browse the art prints collection at boutique.louvre.fr/en/products/400047-art-prints/"
        ),
    },
    {
        "id": "the_dying_slave",
        "name": "The Dying Slave",
        "artist": "Michelangelo Buonarroti",
        "year": "1513–16",
        "type": "sculpture",
        "period": "Italian Renaissance / High Renaissance, 1513–16",
        "location": "Louvre, Salle 403 (Denon Wing — Michelangelo Gallery)",
        "key_facts": (
            "Marble, height 229 cm (90 in). "
            "Carved 1513–16 by Michelangelo as part of the never-completed Tomb of Pope Julius II. "
            "Given by Michelangelo to Roberto Strozzi in 1546, who took it to France as a gift to King Francis I. "
            "Entered the Louvre in 1794 during the Revolution. "
            "Its companion piece, The Rebellious Slave, is displayed alongside it in the same room."
        ),
        "visual_description": (
            "A young male figure stands with his eyes closed and his head tilted back, "
            "his left arm raised and bent so that the hand rests behind his head. "
            "His body twists gently, the right hip pushed forward, the weight shifting as if in sleep or surrender. "
            "A band crosses his chest — a reminder of his captive status. "
            "Behind his left shoulder, a half-formed face barely emerges from the rough marble — "
            "possibly an ape, possibly the unfinished figure of another slave or captive. "
            "The surface transitions from the high polish of the figure's skin "
            "to rough, unfinished areas at the base and back — "
            "the stone from which he is still, in some sense, emerging."
        ),
        "historical_context": (
            "Pope Julius II commissioned Michelangelo to create a monumental freestanding tomb in 1505 — "
            "a project that would have been the largest sculptural monument since antiquity, "
            "featuring over 40 life-size figures. "
            "The project was repeatedly interrupted: Julius diverted Michelangelo to paint the Sistine Chapel ceiling, "
            "then died in 1513, and successive popes scaled back the commission. "
            "The 'Slaves' or 'Prisoners' were intended for the lower tier of the tomb, "
            "symbolising the provinces conquered by Julius or the liberal arts imprisoned by his death. "
            "After decades of delays, the final tomb installed in San Pietro in Vincoli (Rome) in 1545 "
            "was a fraction of the original plan. "
            "Michelangelo gave the two Louvre Slaves to Roberto Strozzi, a Florentine exile in Lyon, "
            "who presented them to King Francis I of France."
        ),
        "technique": (
            "Michelangelo's method — which he described philosophically as 'releasing the figure from the stone' — "
            "involved attacking the block from the front, working inward as if uncovering a form already present. "
            "He rarely used full preparatory models, preferring to discover the figure through the act of carving. "
            "The contrapposto of the Dying Slave is subtle but masterly: "
            "the twist of the torso, the raised arm, and the dropped hip create a gentle spiral "
            "that animates the figure without drama. "
            "The surface polish on the skin areas was achieved through progressive abrasion — "
            "from iron chisels to pumice to cloth — producing the warm luminosity "
            "that characterises Michelangelo's mature marble work. "
            "The deliberately unfinished areas behind the figure are thought to be intentional, "
            "reinforcing the sense of a being not yet fully freed from matter."
        ),
        "story": (
            "The unfinished monkey-like face emerging from behind the Slave's shoulder "
            "has puzzled scholars for centuries. "
            "Some interpret it as a symbol of the arts (the 'ape of nature'), others as a second captive, "
            "and others argue it was simply abandoned when Michelangelo moved on. "
            "Michelangelo left many works unfinished — he called these non-finito pieces — "
            "and some scholars believe he viewed incompletion as philosophically meaningful: "
            "the struggle of form against matter, never fully resolved. "
            "The two Louvre Slaves passed through French royal collections before entering the Louvre "
            "during the Revolution, when the royal collections were nationalised. "
            "They are among the very few Michelangelo sculptures outside Italy — "
            "the others being the Bruges Madonna in Belgium and works in St. Peter's Basilica in Rome — "
            "making them uniquely precious to the Louvre."
        ),
        "content": (
            "The Dying Slave is a marble sculpture by Michelangelo, carved between 1513 and 1516 "
            "for the never-completed Tomb of Pope Julius II. Standing 229 cm tall, the figure — "
            "a young man with closed eyes and one arm raised behind his head — appears to drift "
            "between sleep, ecstasy, and death. The deliberate contrast between the polished skin "
            "and rough unfinished stone reinforces the sense of a being still emerging from matter. "
            "Given by Michelangelo to a Florentine exile and eventually presented to Francis I of France, "
            "it entered the Louvre during the Revolution. "
            "It is one of the very few Michelangelo sculptures outside Italy."
        ),
        "shop": (
            "The Louvre boutique sells a hand-patinated resin replica of the Dying Slave (31 × 9 × 7 cm, €259), "
            "produced using 3D scanning of the original marble for exceptional accuracy. "
            "Art prints are also available from €22. "
            "Browse at boutique.louvre.fr/en/product/18453-dying-slave-michelangelo-buonarroti.html"
        ),
    },
    {
        "id": "the_crouching_scribe",
        "name": "The Seated Scribe (The Crouching Scribe)",
        "artist": "Unknown (Egyptian Old Kingdom)",
        "year": "c. 2620–2500 BC",
        "type": "sculpture",
        "period": "Egyptian Old Kingdom, 4th–5th Dynasty, c. 2620–2500 BC",
        "location": "Louvre, Salle 635 (Egyptian Antiquities)",
        "key_facts": (
            "Painted limestone with rock crystal and magnesite eyes, height 53.7 cm (21 in). "
            "Created c. 2620–2500 BC during the 4th or 5th Dynasty of the Egyptian Old Kingdom. "
            "Discovered at Saqqara (the necropolis of Memphis) in 1850 by Auguste Mariette. "
            "The inlaid crystal eyes create a vivid, almost unsettling sense of alertness. "
            "One of the most recognised works of ancient Egyptian art in the world."
        ),
        "visual_description": (
            "A man sits cross-legged on the floor in the formal scribal position, "
            "his papyrus scroll unrolled across his lap, his right hand raised as if holding a reed pen mid-sentence. "
            "He looks directly forward with startling intensity — his eyes are inlaid with rock crystal "
            "over painted irises of brown and white, and the whites are magnesite. "
            "The effect under museum lighting is a gaze so alive and direct it stops visitors in their tracks. "
            "He is slightly overweight — a sign of prosperity and a sedentary life of learning — "
            "with a soft belly, rounded shoulders, and the relaxed hands of a man at ease in his work. "
            "The skin is painted red-brown (the Egyptian convention for male figures), "
            "and the black hair is still vivid after 4,500 years."
        ),
        "historical_context": (
            "Scribes occupied a privileged position in ancient Egyptian society. "
            "In a civilisation of mostly illiterate farmers, a man who could read and write "
            "had access to administration, religious ritual, and royal service. "
            "Scribe statues were placed in tombs as part of the funerary equipment — "
            "the figure was meant to perform its duty in the afterlife, "
            "eternally recording the offerings and prayers made to the deceased. "
            "The statue was found in the mastaba tomb of an unknown official at Saqqara "
            "by French archaeologist Auguste Mariette in 1850. "
            "Saqqara was the cemetery of Memphis, Egypt's ancient capital, "
            "and was the site of some of the oldest monumental burials in the world, "
            "including the Step Pyramid of Djoser directly above the dig site."
        ),
        "technique": (
            "The Scribe is carved from limestone — a soft, easily worked stone abundant in Egypt. "
            "The surface was coated in a fine gesso ground and then painted in mineral pigments: "
            "red ochre for the skin, carbon black for the hair, white calcite for the kilt. "
            "The eyes are a tour de force of ancient craftsmanship: "
            "the cornea is polished rock crystal, cut to a convex curve to replicate the curvature of the eye; "
            "behind it the iris is painted; the white is magnesite; and copper clips hold it all in place. "
            "The result convinced ancient visitors — and modern ones — that they are looking at a living person. "
            "Egyptian sculptors worked within strict canonical proportions, "
            "but the Scribe's slight corpulence and individualised face suggest portraiture rather than idealisation."
        ),
        "story": (
            "When Auguste Mariette and his team uncovered the Scribe at Saqqara in 1850, "
            "workers reportedly stopped and stared — the inlaid eyes were so lifelike "
            "that the figure seemed to gaze back at them from across forty-five centuries. "
            "The identity of the man depicted — his name, his title, whose tomb he served — "
            "remains completely unknown. No inscription survives to identify him. "
            "He is, paradoxically, one of the most famous anonymous people in history: "
            "recognised by millions, known to no one. "
            "The crystal eyes have been studied using modern optical techniques: "
            "the convex shape of the cornea refracts light exactly as a real eye does, "
            "which is why the statue seems to watch the viewer from every angle in the room."
        ),
        "content": (
            "The Seated Scribe is a painted limestone figure from ancient Egypt, "
            "created c. 2620–2500 BC during the 4th or 5th Dynasty of the Old Kingdom. "
            "Measuring 53.7 cm, he sits cross-legged with a papyrus scroll across his lap, "
            "looking directly at the viewer through inlaid rock crystal eyes so precisely made "
            "that they seem to follow you across the room. "
            "Found at Saqqara in 1850 by Auguste Mariette, his identity is completely unknown — "
            "he is one of the most famous anonymous people in human history. "
            "He is among the most recognised works of ancient Egyptian art in the world."
        ),
        "shop": (
            "The Louvre boutique sells a hand-patinated resin replica of the Seated Scribe "
            "(23.5 × 19.5 × 15 cm, €440), capturing the striking inlaid-eye detail of the original. "
            "A small enamel pin is also available at €7.95 — a wearable tribute to one of history's "
            "most famous anonymous faces. "
            "Browse at boutique.louvre.fr/en/product/11940-seated-scribe.html"
        ),
    },
    {
        "id": "bastet_cat_statue",
        "name": "Bastet Cat Statue",
        "artist": "Unknown (Egyptian Late Period)",
        "year": "c. 664–332 BC",
        "type": "sculpture",
        "period": "Egyptian Late Period, 664–332 BC",
        "location": "Louvre, Salle 630 (Egyptian Antiquities)",
        "key_facts": (
            "Bronze with gold earrings, height approx. 28–35 cm. "
            "Created during the Egyptian Late Period (c. 664–332 BC), 26th–30th Dynasty. "
            "Bastet (also Bast) was the goddess of protection, fertility, and the home, depicted as a cat or cat-headed woman. "
            "Cat worship reached its peak during the Late Period; thousands of bronze cat votive figures were produced. "
            "The Louvre holds several examples from temple deposits and private dedications."
        ),
        "visual_description": (
            "A sleek bronze cat sits in the formal Egyptian pose: perfectly upright, tail curled around its front paws, "
            "ears pricked forward in alert attention. "
            "The body is rendered with elegant economy — smooth, simplified, yet unmistakably feline in its posture. "
            "The eyes are often inlaid with glass or stone, catching light with an amber or green gleam. "
            "Gold hoop earrings pierce the ears, and a broad collar necklace may be incised around the neck. "
            "Some examples carry a scarab pendant on the chest or a small aegis (a shield-amulet) at the throat — "
            "symbols of protection and divine power. "
            "The dark patina of the bronze gives the figure a quiet, watchful dignity."
        ),
        "historical_context": (
            "Bastet was originally a fierce lioness deity, a daughter of Ra, the sun god. "
            "Over time her iconography softened from lion to domestic cat, "
            "and she became associated with home, protection, motherhood, and music. "
            "Her main cult centre was at Bubastis (modern Tell Basta) in the Nile Delta, "
            "where the Greek historian Herodotus described one of the largest festivals in Egypt: "
            "hundreds of thousands of pilgrims sailed to Bubastis each spring, "
            "singing and celebrating along the Nile. "
            "During the Late Period, the practice of dedicating bronze animal votives to temple deities exploded — "
            "worshippers would commission a bronze cat, have it blessed, "
            "and deposit it in a sacred animal cemetery at the temple. "
            "Archaeologists at Bubastis found hundreds of thousands of cat mummies and bronze figures."
        ),
        "technique": (
            "Late Period Egyptian bronze casting used the lost-wax (cire perdue) process: "
            "the figure was modelled in wax around a clay core, "
            "then encased in an outer clay mould. "
            "When the mould was fired, the wax melted away (hence 'lost wax'), "
            "leaving a cavity that was filled with molten bronze. "
            "After cooling, the outer mould was broken away and the figure was finished by hand — "
            "chiselled, polished, and engraved with details. "
            "Inlaid eyes of glass or coloured stone were set after casting. "
            "The quality of workmanship varies widely: "
            "some figures were produced in large quantities for mass devotion, "
            "while elite examples — like the finest Louvre specimens — "
            "show extraordinary precision and elegant proportions."
        ),
        "story": (
            "The ancient Egyptians held cats in such reverence that killing one — "
            "even accidentally — could be punished by death. "
            "When a household cat died of natural causes, its owners would go into mourning, "
            "shaving their eyebrows as a sign of grief. "
            "Herodotus reported that during a fire, Egyptians would neglect saving their property "
            "to rescue cats from the flames. "
            "Roman and Greek visitors found this devotion baffling and wrote about it with wonder. "
            "The vast cat cemeteries at Bubastis and other sites were largely destroyed in the 19th century "
            "when farmers ground up the mummified cats as fertiliser. "
            "Thousands of bronze votive cats were exported to Europe as curiosities, "
            "filling museum collections and private hands. "
            "The best of these are now among the most delicate and quietly beautiful objects in the ancient world."
        ),
        "content": (
            "The Bastet Cat Statue is an Egyptian bronze sculpture from the Late Period (c. 664–332 BC), "
            "depicting the goddess Bastet in her feline form. "
            "Sitting perfectly upright, adorned with gold earrings and an incised collar, "
            "the cat embodies the protective, maternal power of one of Egypt's most beloved deities. "
            "Produced by lost-wax casting and often finished with inlaid glass eyes, "
            "these votive figures were dedicated by worshippers at temples across the Nile Delta. "
            "Bastet worship reached its peak during the Late Period, when her festival at Bubastis "
            "attracted hundreds of thousands of pilgrims — one of the largest religious gatherings in the ancient world."
        ),
        "shop": (
            "The Louvre boutique offers several Bastet cat reproductions. "
            "A hand-patinated resin replica of the Cat of the Goddess Bastet (16 × 7 × 9 cm) is available, "
            "as well as a bronze cast version and a version with a decorative necklace collar. "
            "An enamel pin of the Bastet cat is also available at €7.95. "
            "Browse the full collection at boutique.louvre.fr/en/products/400746-the-cat-bastet/"
        ),
    },
    {
        "id": "miles_franklin_statue",
        "name": "Miles Franklin Statue",
        "artist": "Jacek Luszczyk",
        "year": "2003",
        "type": "sculpture",
        "period": "Contemporary Australian Public Art, 2003",
        "location": "MacMahon Street, Hurstville, Sydney (near Ritz Hotel)",
        "key_facts": (
            "Bronze public sculpture, life-size seated figure. "
            "Created in 2003 by Polish-Australian sculptor Jacek Luszczyk. "
            "Commemorates Miles Franklin (1879–1954), one of Australia's most celebrated authors. "
            "Located on MacMahon Street, Hurstville, near the heritage Ritz Hotel, in the Georges River area of Sydney. "
            "Temporarily removed in 2021 during street rejuvenation works and reinstalled in 2023 on a new plinth. "
            "Sited near the former council chambers where Franklin completed some of her literary work, "
            "and close to her former residence at Grey Street, Carlton, and her office in the Jolley's Building, Forest Road, Hurstville."
        ),
        "visual_description": (
            "A life-size bronze seated figure of a woman in early twentieth-century dress, "
            "depicted in a relaxed, contemplative pose as if pausing mid-thought or mid-sentence. "
            "She is placed on a bench or low plinth, bringing her to the eye level of passers-by "
            "and inviting an informal, personal encounter rather than the distant grandeur of a pedestal monument. "
            "Her clothing reflects the fashion of the early 1900s — the period of her most famous work. "
            "The bronze surface has developed a warm patina from years of outdoor exposure in the Sydney climate. "
            "The figure faces the street, situated against the backdrop of the heritage Ritz Hotel facade, "
            "connecting the literary past of the area with its present-day urban character."
        ),
        "historical_context": (
            "Miles Franklin — full name Stella Maria Sarah Miles Franklin — was born on 14 October 1879 "
            "in Talbingo, New South Wales, and died on 19 September 1954. "
            "She published her debut novel My Brilliant Career in 1901 at age 21, "
            "a semi-autobiographical work set in rural Australia that captured the independent spirit "
            "of a young woman navigating the constraints of colonial society. "
            "The novel was championed by Henry Lawson and became a landmark of Australian literature. "
            "Franklin had significant personal connections to the Hurstville and Georges River area: "
            "she maintained a residence at Grey Street, Carlton, and worked from an office in the Jolley's Building "
            "on Forest Road, Hurstville. She wrote All That Swagger (1936) here. "
            "Through her will, she established the Miles Franklin Literary Award, "
            "Australia's most prestigious annual prize for literature about 'Australian life in any of its phases.' "
            "Sculptor Jacek Luszczyk was commissioned by Georges River Council to create the work in 2003."
        ),
        "technique": (
            "The statue is cast in bronze using the lost-wax (cire perdue) process — "
            "the traditional method for large-scale figurative public sculpture. "
            "A clay or wax model is built over an armature, "
            "then encased in a mould; molten bronze is poured in after the wax is burned away. "
            "The resulting cast is cleaned, chased, and patinated to achieve the final surface colour. "
            "Jacek Luszczyk trained in classical figurative sculpture and is known for works "
            "that prioritise naturalism and psychological presence over stylisation. "
            "The decision to seat the figure at street level rather than raise her on a tall pedestal "
            "is a characteristic of contemporary public memorial sculpture: "
            "it creates democratic accessibility, allowing visitors to sit alongside the figure "
            "and engage with her as a human presence rather than a distant monument."
        ),
        "story": (
            "Miles Franklin spent years in the United States and London before returning to Australia in 1932, "
            "settling eventually in Carlton, NSW, in the Georges River area. "
            "It was here, in the suburb adjacent to Hurstville, that she wrote All That Swagger (1936), "
            "working from her local office in the Jolley's Building on Forest Road. "
            "She never married and devoted her later life to advocating for Australian writers and literature. "
            "When she died in 1954 she left the bulk of her estate to fund the literary award that bears her name — "
            "the Miles Franklin Award — which has since been won by Patrick White, Thomas Keneally, "
            "Tim Winton, and many other major Australian authors. "
            "The statue was temporarily removed in 2021 when MacMahon Street underwent rejuvenation works. "
            "Its return in 2023 — on a new plinth, facing the Ritz Hotel — was welcomed by the local community "
            "as a reaffirmation of the area's literary heritage. "
            "EggMan28's 3D Gaussian splat capture of the statue (2022) now exists as a digital twin, "
            "linking the physical work to its virtual counterpart in XR."
        ),
        "content": (
            "The Miles Franklin Statue is a bronze public sculpture by Jacek Luszczyk, unveiled in 2003 "
            "on MacMahon Street, Hurstville, in Sydney's Georges River area. "
            "It commemorates Stella Miles Franklin (1879–1954), author of My Brilliant Career (1901) "
            "and founder of Australia's most prestigious literary prize. "
            "Depicted as a life-size seated figure in early twentieth-century dress, "
            "the statue is placed at street level beside the heritage Ritz Hotel, "
            "near the office and former residence Franklin used during her years in Hurstville. "
            "She wrote All That Swagger here in 1936. "
            "The statue was reinstalled in 2023 after temporary removal for street works."
        ),
        "shop": (
            "The Miles Franklin Statue is a public artwork commissioned by Georges River Council. "
            "There is no official merchandise store for this work. "
            "For information about the Miles Franklin Literary Award and related publications, "
            "visit the official award website at milesfranklin.com.au"
        ),
    },
    {
        "id": "air_maillol",
        "name": "Air",
        "artist": "Aristide Maillol",
        "year": "1938",
        "type": "sculpture",
        "period": "Modern / Post-Art Nouveau, 1938",
        "location": "Jardin des Tuileries, Louvre Estate, Paris",
        "key_facts": (
            "Lead (original maquette in plaster), 130 × 240 × 93.3 cm. "
            "Created 1938 by Aristide Maillol; cast in an edition of six after the artist's death. "
            "Model: Dina Vierny, who posed for Maillol from age 15 and became his muse for his final decade. "
            "Displayed in the Jardin des Tuileries — the formal garden between the Louvre and the Place de la Concorde. "
            "Other casts are at the Kröller-Müller Museum, Yale University Art Gallery, "
            "J. Paul Getty Museum, Norton Simon Museum, and Kimbell Art Museum."
        ),
        "visual_description": (
            "A woman floats horizontally in mid-air, her body parallel to the ground, "
            "arms extended above her head, legs trailing behind. "
            "She is nude, the body rounded and full — Maillol's characteristic ideal of feminine weight and warmth. "
            "There is no support visible beneath her; she simply hovers, "
            "suggesting total surrender to the element she embodies. "
            "The lead surface, cast after the artist's death, has a dark pewter-grey patina "
            "that absorbs light rather than reflecting it, giving the figure a quiet, earthbound gravitas "
            "even as the pose implies weightlessness. "
            "The proportions are monumental: seen in the Tuileries garden, "
            "she lies against a backdrop of sky and formal hedges, "
            "and the tension between her floating pose and her material weight is palpable."
        ),
        "historical_context": (
            "Aristide Maillol (1861–1944) trained as a tapestry designer before turning to sculpture in his forties. "
            "Working in reaction against the turbulent expressionism of Rodin, "
            "he developed a language of serene, monumental female nudes "
            "that drew on ancient Mediterranean sculpture — particularly Greek archaic and classical work — "
            "rather than on Baroque or Romantic precedents. "
            "He worked with Dina Vierny from 1934, when she was fifteen and he was seventy-three. "
            "She modelled for all his late works, including Air, and later founded the Musée Maillol in Paris "
            "to preserve his legacy. "
            "Air was created in 1938, a year in which Europe was sliding toward catastrophe — "
            "Spain's Civil War had begun, Hitler had annexed Austria. "
            "Maillol's serene nudes offer an almost provocative alternative to the era's anxiety."
        ),
        "technique": (
            "Maillol's working method was deeply traditional: he modelled directly in clay or plaster, "
            "working from the live model over many sessions. "
            "He preferred to work at a slow pace, returning repeatedly to adjust proportions "
            "until the figure achieved the balance he sought. "
            "Air's horizontal pose was an extreme technical challenge in plaster — "
            "the cantilever of arms and legs could crack the material under its own weight. "
            "The final cast in lead (rather than the more common bronze) was chosen posthumously "
            "for its density and colour: lead's dark, matte surface suits the quiet gravity of the piece. "
            "Unlike Rodin, who often left rough surfaces to suggest process and emotion, "
            "Maillol smoothed and simplified — every plane is resolved, "
            "every surface calm, achieving what he called 'the silence of the figure.'"
        ),
        "story": (
            "Dina Vierny was fifteen years old when the painter Pierre Bonnard introduced her to Maillol in 1934. "
            "Maillol declared immediately that she was 'la Méditerranée' — the embodiment of "
            "the classical Mediterranean ideal he had been seeking all his life. "
            "She modelled for him for ten years, through his final and most celebrated works. "
            "During the German occupation of France, she used her position as a known artist's model "
            "as cover to smuggle Jewish refugees and resistance members across the Pyrenees into Spain. "
            "She was arrested by the Gestapo in 1943 and spent six months in prison before Maillol, "
            "who had contacts in the collaborationist administration, secured her release. "
            "After his death in 1944 — in a car accident — Vierny spent the next fifty years "
            "managing his estate, organising exhibitions, and establishing the Musée Maillol in Paris. "
            "Air floats above the Tuileries because of her."
        ),
        "content": (
            "Air is a lead sculpture by Aristide Maillol, modelled in 1938 and cast posthumously in an edition of six. "
            "A nude woman floats horizontally, arms extended, in total surrender to the element she represents. "
            "The model was Dina Vierny — Maillol's fifteen-year-old muse who later became a French Resistance hero "
            "and founder of the Musée Maillol. "
            "Displayed in the Jardin des Tuileries on the Louvre estate, "
            "Air embodies Maillol's lifelong pursuit of Mediterranean serenity — "
            "a figure of absolute calm created on the eve of the Second World War."
        ),
        "shop": (
            "Air by Maillol is displayed in the Jardin des Tuileries and is not sold by the Louvre boutique. "
            "The Musée Maillol in Paris (61 rue de Grenelle, 7th arrondissement) has a dedicated gift shop "
            "with Maillol-related publications, prints, and objects. "
            "Art prints of works from the Tuileries garden sculpture collection may also be available at boutique.louvre.fr"
        ),
    },
    {
        "id": "la_nuit_maillol",
        "name": "La Nuit (Night)",
        "artist": "Aristide Maillol",
        "year": "1902–1909",
        "type": "sculpture",
        "period": "Modern / Post-Art Nouveau, 1902–1909",
        "location": "Jardin des Tuileries (Carrousel Garden), Paris — installed 1964",
        "key_facts": (
            "Bronze, H: 110 cm, W: 78 cm, D: 116 cm. "
            "Modelled between 1902 and 1909 by Aristide Maillol; the bronze cast installed in the Tuileries in 1964. "
            "Depicts a seated female nude with bent legs, arms resting on her knees, head bowed and buried in her forearms — as if asleep. "
            "Part of the open-air collection of Maillol's works established in the Tuileries by Dina Vierny and André Malraux in 1964. "
            "Other casts exist at the Metropolitan Museum of Art, New York."
        ),
        "visual_description": (
            "A compact, self-contained female figure sits on the ground with her knees drawn up to her chest. "
            "Her arms are folded protectively over her knees, and her head is bowed forward, resting on her forearms — "
            "completely hidden, turned inward, withdrawn from the world. "
            "The pose is one of absolute enclosure: no face is visible, no limb extends outward. "
            "The bronze surface carries a warm dark patina from decades of outdoor exposure. "
            "Unlike Maillol's more expansive reclining figures, La Nuit is dense and concentrated, "
            "a sphere of weight and sleep compressed into itself. "
            "Seen in the Tuileries garden, the figure appears both monumental and deeply private."
        ),
        "historical_context": (
            "Aristide Maillol (1861–1944) made female nudes almost exclusively, "
            "exploring the elemental and sensuous qualities of the human body without literary or symbolic ornamentation. "
            "La Nuit was modelled over seven years between 1902 and 1909, "
            "a period when Maillol was moving away from the turbulent expressionism of Rodin "
            "toward a quieter, more archaic monumentality. "
            "The Tuileries bronze was cast and installed in 1964 as part of a major public initiative "
            "led by Dina Vierny — Maillol's model and lifelong champion — and André Malraux, "
            "then France's Minister of Cultural Affairs, to create an open-air Maillol museum in Paris. "
            "The collection of eighteen works placed throughout the Tuileries and Carrousel gardens "
            "transformed the formal French garden into one of the world's great outdoor sculpture parks."
        ),
        "technique": (
            "Maillol modelled La Nuit in clay, working directly from the figure over many sessions. "
            "He preferred slow, deliberate modelling — returning repeatedly to adjust the volumes "
            "until the mass achieved the stillness and balance he sought. "
            "The compactness of the pose presented no structural challenges (unlike his horizontal figures), "
            "allowing the weight to rest entirely through the seated base. "
            "The bronze was cast using the lost-wax process and finished with a dark patina "
            "suited to outdoor display. "
            "Maillol's approach — smooth, simplified surfaces, resolving every plane into calm — "
            "contrasts sharply with Rodin's rough, process-revealing surfaces and is fully expressed here."
        ),
        "story": (
            "La Nuit belongs to a group of Maillol's elemental works named after natural forces and states of being — "
            "alongside Air, L'Hommage à Cézanne, and others — each embodying a quality rather than a narrative. "
            "Where Air floats horizontally in surrender, La Nuit curls inward in protective sleep. "
            "Dina Vierny, who posed for Maillol from the age of fifteen and managed his estate after his death in 1944, "
            "worked with André Malraux to secure the permanent placement of Maillol's bronzes in the Tuileries. "
            "The collection she assembled there remains the largest concentration of Maillol's outdoor work in the world. "
            "A cast of La Nuit is also held at the Metropolitan Museum of Art in New York, "
            "where it is one of the most quietly powerful works in the collection."
        ),
        "content": (
            "La Nuit (Night) is a bronze sculpture by Aristide Maillol, modelled between 1902 and 1909 "
            "and installed in the Jardin des Tuileries in 1964. "
            "A seated female nude with her head buried in her folded arms, the work embodies enclosure, "
            "sleep, and inward withdrawal — the opposite of Maillol's floating Air nearby. "
            "Part of the open-air collection established by Dina Vierny and André Malraux, "
            "it stands in the Carrousel garden as one of the finest examples of Maillol's monumental, meditative style."
        ),
    },
    {
        "id": "hommage_a_cezanne_maillol",
        "name": "L'Hommage à Cézanne",
        "artist": "Aristide Maillol",
        "year": "1912",
        "type": "sculpture",
        "period": "Modern / Post-Art Nouveau, 1912",
        "location": "Jardin des Tuileries (Carrousel Garden), Paris — lead cast installed 1964",
        "key_facts": (
            "Lead cast, Carrousel Garden, Tuileries, Paris. Original stone version at Musée d'Orsay, Paris. "
            "Created 1912 by Aristide Maillol; Tuileries lead cast installed 1964. "
            "Commissioned by the city of Aix-en-Provence to honour Paul Cézanne — the commission was rejected by the city, "
            "and the work eventually found its way to Paris. "
            "Depicts a semi-reclining nude female figure with her left arm resting on her slightly raised left knee."
        ),
        "visual_description": (
            "A nude woman reclines in a semi-horizontal pose — her upper body slightly raised, "
            "her left arm resting on her bent left knee, her legs extending in a long, relaxed diagonal. "
            "The body is full and rounded in Maillol's characteristic Mediterranean ideal, "
            "every surface resolved into a calm, unhurried plane. "
            "The lead surface has the dark, matte quality of old pewter, absorbing rather than reflecting light "
            "and giving the figure a quiet, earthbound presence even in its reclining repose. "
            "Seen in the Carrousel garden, the figure lies low against the formal hedges and gravel, "
            "a horizontal counterpoint to the vertical cypress and the movement of visitors above."
        ),
        "historical_context": (
            "Paul Cézanne (1839–1906), the Post-Impressionist painter, died in 1906 and was immediately recognised "
            "as one of the foundational figures of modern art. "
            "The city of Aix-en-Provence — Cézanne's birthplace — commissioned Maillol in 1912 to create a monument in his honour. "
            "Maillol proposed not a portrait or a narrative scene but an abstract female nude, "
            "in keeping with his belief that sculpture should embody elemental qualities rather than commemorate individuals. "
            "Aix-en-Provence rejected the work, finding it too abstract for a public memorial. "
            "The advocate Frantz Jourdain championed the sculpture and helped bring it to Paris. "
            "The original stone version entered the Musée d'Orsay's collection. "
            "The lead cast now in the Tuileries was placed there in 1964 by Dina Vierny and André Malraux "
            "as part of the open-air Maillol collection."
        ),
        "technique": (
            "Maillol modelled the work in clay from the live figure, then had it cast in stone for the original version "
            "and in lead for the Tuileries edition. "
            "Lead was chosen for the outdoor casts — as with Air — for its density, durability, and dark matte surface, "
            "which Maillol and Vierny felt suited the meditative, earthbound quality of his figures. "
            "The semi-reclining pose demanded careful attention to the distribution of mass: "
            "Maillol resolved the composition so that the raised knee creates a stabilising diagonal "
            "that anchors the figure visually without making it appear rigid. "
            "The smooth, simplified surfaces are characteristic of his mature technique."
        ),
        "story": (
            "The rejection by Aix-en-Provence is one of the notable ironies of 20th-century French art: "
            "a city commissioning a monument to its most celebrated son, then refusing the result because it was too modern. "
            "Maillol's decision to honour Cézanne not with a portrait but with a generic female nude "
            "reflected his deep conviction that great art transcends biography — "
            "a view that Cézanne himself would likely have endorsed. "
            "The stone original now in the Musée d'Orsay is considered one of Maillol's finest early works. "
            "The Tuileries lead cast, placed there by Dina Vierny in 1964, "
            "stands among eighteen Maillol bronzes that transformed the formal French garden "
            "into an open-air museum — the largest concentration of Maillol's outdoor sculpture in the world."
        ),
        "content": (
            "L'Hommage à Cézanne is a sculpture by Aristide Maillol, created in 1912 as a public monument "
            "to honour the Post-Impressionist painter Paul Cézanne. "
            "Commissioned by Aix-en-Provence and rejected for being too abstract, "
            "the work depicts a semi-reclining nude female figure — Maillol's characteristic form for embodying elemental qualities. "
            "The original stone version is at the Musée d'Orsay; the lead cast installed in the Carrousel garden "
            "of the Tuileries in 1964 is part of the open-air Maillol collection assembled by Dina Vierny and André Malraux."
        ),
    },
    {
        "id": "la_siesta_foyatier",
        "name": "La Siesta",
        "artist": "Denis Foyatier",
        "year": "1848",
        "type": "sculpture",
        "period": "French Neoclassicism, 19th century",
        "location": "Louvre, Salle 225, Richelieu wing, Level 0 — Department of Medieval, Renaissance and Modern Sculpture",
        "key_facts": (
            "Marble, H: 76 cm, W: 154.5 cm, D: 59 cm. "
            "Signed 'Foyatier 1848' on the pillow. "
            "Created by Denis Foyatier (1793–1863), one of the major French Neoclassical sculptors of the 19th century. "
            "This is a replica of the marble exhibited at the Salon of 1834 and later shown at the Universal Expositions of 1855 and 1889. "
            "Entered the Louvre in 1897 as a donation from General Denis-François-Félix Deloye on behalf of the sculptor's daughters. "
            "Displayed in Salle 225, Richelieu wing, Level 0."
        ),
        "visual_description": (
            "A reclining female figure lies on her side in a state of complete, relaxed sleep — the siesta of the title. "
            "Her body is draped in soft fabric that clings to and pools around her form, "
            "her head resting on a pillow (on which the sculptor's signature is carved). "
            "The pose is one of absolute repose: limbs loose, expression peaceful, every muscle surrendered to rest. "
            "The marble surface is polished to a smooth, skin-like finish on the figure "
            "while the drapery and pillow are rendered with virtuoso textile detail. "
            "At 154.5 cm wide, the sculpture has the horizontal scale of a reclining figure seen life-size. "
            "The composition is self-contained and tranquil — a rare moment of everyday rest elevated to monument."
        ),
        "historical_context": (
            "Denis Foyatier (1793–1863) was one of the prominent French Neoclassical sculptors of the early 19th century, "
            "best known for his monumental works including Spartacus (1830) and various royal commissions. "
            "La Siesta was first exhibited at the Salon of 1834, where the reclining figure's naturalism "
            "and intimate subject matter — sleep, rest, the domestic moment — attracted attention. "
            "Foyatier subsequently created the 1848 marble now in the Louvre, "
            "which was shown at the Universal Expositions of 1855 and 1889, bringing it to international audiences. "
            "The Louvre classifies it in its Department of Medieval, Renaissance and Modern Sculpture, "
            "reflecting its place within the long French tradition of monumental marble carving. "
            "The work entered the collection in 1897 through the generosity of General Deloye, "
            "acting on behalf of the sculptor's daughters — a final act of filial care for a father's legacy."
        ),
        "technique": (
            "Foyatier worked within the French Neoclassical tradition, in which marble carving was the supreme sculptural medium "
            "and technical mastery of surface — skin, fabric, hair, stone — was the benchmark of excellence. "
            "La Siesta demonstrates his skill in differentiating textures within a single block: "
            "the smooth warmth of flesh, the soft folds of drapery, and the firm surface of the pillow "
            "are rendered in the same white marble through progressive chiselling and abrasion. "
            "The reclining pose, while appearing simple, requires careful structural planning: "
            "the weight of the horizontal figure must be distributed through the base "
            "without the composition appearing stiff or top-heavy. "
            "Foyatier's solution — the easy, natural curve of the body — makes the technical achievement invisible."
        ),
        "story": (
            "The subject of La Siesta — an ordinary woman sleeping in the afternoon — "
            "was a quietly radical choice for a major Salon work in 1834. "
            "Academic sculpture of the period favoured mythological heroines, allegorical figures, and historical subjects. "
            "A sleeping contemporary woman, without wings or attributes or narrative context, "
            "was closer to genre painting than to monument-making. "
            "Yet the work succeeded: it was shown at two Universal Expositions and entered the national collection. "
            "The sculptor's daughters kept the work for decades after his death in 1863 "
            "before donating it through General Deloye in 1897 — more than thirty years after Foyatier's death — "
            "ensuring it reached the institution best equipped to preserve it. "
            "It now rests in Salle 225 of the Richelieu wing, a quiet corner of the Louvre "
            "where ordinary rest has been made permanent in marble."
        ),
        "content": (
            "La Siesta is a marble sculpture by Denis Foyatier (1793–1863), dated 1848 and displayed in Salle 225, "
            "Richelieu wing, Level 0 of the Louvre. "
            "Measuring 154.5 cm wide, it depicts a reclining female figure in complete, natural sleep — "
            "the sculptor's signature carved into her pillow. "
            "A replica of the marble first shown at the Salon of 1834, "
            "it was subsequently exhibited at the Universal Expositions of 1855 and 1889 "
            "before entering the Louvre in 1897 as a gift from the sculptor's daughters. "
            "One of the finest examples of French Neoclassical marble carving in the Louvre's collection."
        ),
        "shop": (
            "The Louvre boutique does not currently offer dedicated merchandise for La Siesta by Denis Foyatier. "
            "Art prints of works from the Louvre's sculpture collection are available from €22. "
            "Browse the sculpture collection at boutique.louvre.fr/en/products/400013-sculpture/"
        ),
    },
]
