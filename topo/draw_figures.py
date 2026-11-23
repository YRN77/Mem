#!/usr/bin/env python3
"""Dessine les figures du chapitre 4 (topologies avant/après, maquette, démarche) en PNG."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = "/data/user/0/ai.antigem/files/home/projects/topo/png"
os.makedirs(OUT, exist_ok=True)

FONT = "/system/fonts/DroidSans.ttf"
FONT_B = "/system/fonts/DroidSans-Bold.ttf"

# palette
INK = "#1F2937"
MUTED = "#6B7280"
BLUE, BLUE_F = "#1D4ED8", "#DBEAFE"
GREEN, GREEN_F = "#047857", "#D1FAE5"
AMBER, AMBER_F = "#B45309", "#FEF3C7"
PURPLE, PURPLE_F = "#6D28D9", "#EDE9FE"
RED, RED_F = "#B91C1C", "#FEE2E2"
SLATE, SLATE_F = "#334155", "#E2E8F0"
WHITE = "#FFFFFF"

_fonts = {}


def font(size, bold=False):
    k = (size, bold)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(FONT_B if bold else FONT, size)
    return _fonts[k]


def wrap(draw, text, f, maxw):
    lines = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=f) <= maxw or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def text_block(draw, x, y, w, text, size=24, color=INK, bold=False, align="left", leading=1.25):
    f = font(size, bold)
    lines = wrap(draw, text, f, w)
    lh = int(size * leading)
    for i, ln in enumerate(lines):
        tw = draw.textlength(ln, font=f)
        tx = x if align == "left" else (x + (w - tw) / 2 if align == "center" else x + w - tw)
        draw.text((tx, y + i * lh), ln, font=f, fill=color)
    return y + len(lines) * lh


def box(draw, x, y, w, h, fill, stroke, text="", fz=24, tcol=INK, bold=False,
        radius=14, lw=3, dash=None, align="center", pad=14):
    if dash:
        # pointillés simples
        step = 18
        for i in range(0, w, step):
            draw.line([(x + i, y), (x + min(i + 9, w), y)], fill=stroke, width=lw)
            draw.line([(x + i, y + h), (x + min(i + 9, w), y + h)], fill=stroke, width=lw)
        for i in range(0, h, step):
            draw.line([(x, y + i), (x, y + min(i + 9, h))], fill=stroke, width=lw)
            draw.line([(x + w, y + i), (x + w, y + min(i + 9, h))], fill=stroke, width=lw)
        if radius:
            draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)
            for i in range(0, w, step):
                draw.line([(x + i, y), (x + min(i + 9, w), y)], fill=stroke, width=lw)
                draw.line([(x + i, y + h), (x + min(i + 9, w), y + h)], fill=stroke, width=lw)
            for i in range(0, h, step):
                draw.line([(x, y + i), (x, y + min(i + 9, h))], fill=stroke, width=lw)
                draw.line([(x + w, y + i), (x + w, y + min(i + 9, h))], fill=stroke, width=lw)
    else:
        draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=stroke, width=lw)
    if text:
        f = font(fz, bold)
        lines = wrap(draw, text, f, w - 2 * pad)
        lh = int(fz * 1.22)
        total = len(lines) * lh
        ty = y + (h - total) / 2
        for i, ln in enumerate(lines):
            tw = draw.textlength(ln, font=f)
            tx = x + (w - tw) / 2 if align == "center" else x + pad
            draw.text((tx, ty + i * lh), ln, font=f, fill=tcol)


def arrow(draw, p1, p2, color=MUTED, width=4, label=None, lfz=19, dash=None, lx=0, ly=0):
    x1, y1 = p1
    x2, y2 = p2
    if dash:
        n = 14
        for i in range(0, n, 2):
            xa = x1 + (x2 - x1) * i / n
            ya = y1 + (y2 - y1) * i / n
            xb = x1 + (x2 - x1) * (i + 1) / n
            yb = y1 + (y2 - y1) * (i + 1) / n
            draw.line([(xa, ya), (xb, yb)], fill=color, width=width)
    else:
        draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    s = 17
    a1 = (x2 - s * math.cos(ang - 0.45), y2 - s * math.sin(ang - 0.45))
    a2 = (x2 - s * math.cos(ang + 0.45), y2 - s * math.sin(ang + 0.45))
    draw.polygon([(x2, y2), a1, a2], fill=color)
    if label:
        f = font(lfz)
        tw = draw.textlength(label, font=f)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tx, ty = mx - tw / 2 + lx, my - lfz - 8 + ly
        draw.rounded_rectangle([tx - 6, ty - 4, tx + tw + 6, ty + lfz + 6], radius=5, fill=WHITE)
        draw.text((tx, ty), label, font=f, fill=color)


def canvas(w, h, title, subtitle=None):
    img = Image.new("RGB", (w, h), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline="#D1D5DB", width=2)
    text_block(d, 40, 24, w - 120, title, 30, INK, bold=True)
    if subtitle:
        text_block(d, 40, 70, w - 120, subtitle, 21, MUTED)
    return img, d


# ---------------------------------------------------------------- FIG 4.01
def fig_before():
    W, H = 1700, 900
    img, d = canvas(W, H, "Figure 4.02 — Topologie AVANT SASE : VPN d'accès distant + pare-feu périmétrique",
                    "Tout le trafic converge vers le siège ; un seul tunnel donne un accès réseau étendu (backhaul).")

    # Internet
    box(d, 700, 110, 300, 76, BLUE_F, BLUE, "INTERNET (WAN public)", 23, BLUE, True, radius=38)
    # users
    box(d, 60, 120, 300, 86, BLUE_F, BLUE, "Home laptop\n(poste distant)", 22)
    box(d, 60, 232, 300, 86, BLUE_F, BLUE, "Mobile\n(utilisateur mobile)", 22)
    # firewall + VPN
    box(d, 650, 255, 380, 100, SLATE_F, SLATE, "Pare-feu périmétrique\nOPNsense / pfSense (2 Go)", 23, bold=True)
    box(d, 650, 405, 380, 96, PURPLE_F, PURPLE, "Concentrateur VPN\n(IPsec / SSL-VPN) + annuaire", 23, bold=True)
    # flat network
    d.rounded_rectangle([405, 595, 1330, 795], radius=18, fill="#FFF7ED", outline=RED, width=3)
    text_block(d, 425, 610, 880, "Réseau interne à plat 10.0.0.0/24 — aucune segmentation entre les applications",
               22, RED, bold=True)
    box(d, 440, 675, 265, 80, GREEN_F, GREEN, "CloudDrive\n10.0.0.21", 22)
    box(d, 735, 675, 265, 80, GREEN_F, GREEN, "Finance (ERP)\n10.0.0.22", 22)
    box(d, 1030, 675, 265, 80, GREEN_F, GREEN, "Admin IT\n10.0.0.23", 22)
    # branch
    box(d, 60, 660, 300, 110, GREEN_F, GREEN, "Succursale\nbranch-pc 192.168.10.10", 21)
    text_block(d, 62, 620, 300, "lien MPLS / VPN site-à-site", 17, MUTED)
    arrow(d, (360, 715), (405, 715), GREEN, 4)
    # web paths
    arrow(d, (360, 152), (700, 148), BLUE, 4, "Web / SaaS direct, non filtré", 18, ly=-12)
    # users -> firewall (VPN + backhaul)
    arrow(d, (360, 180), (650, 285), PURPLE, 4, "Tunnel VPN + backhaul web/SaaS", 18, ly=-28)
    arrow(d, (360, 285), (650, 450), PURPLE, 4, "tunnel VPN", 18, ly=18)
    # firewall -> vpn -> flat
    arrow(d, (840, 355), (840, 405), SLATE, 4)
    arrow(d, (840, 501), (840, 595), RED, 4, "accès IP étendu après authentification", 18, ly=8)

    # limitations panel
    d.rounded_rectangle([1390, 100, 1670, 860], radius=14, fill="#FEF2F2", outline=RED, width=2)
    text_block(d, 1408, 118, 244, "Limites constatées", 22, RED, bold=True)
    lims = ["L1  Confiance implicite : le VPN ouvre tout le réseau",
            "L2  Backhaul du trafic web/SaaS par le siège",
            "L3  Règles par adresse IP, sans identité",
            "L4  Journaux dispersés par équipement",
            "L5  Lien unique, aucune bascule",
            "L6  Aucun contrôle des actions ni des contenus cloud"]
    text_block(d, 1408, 165, 240, "\n\n".join(lims), 19, "#7F1D1D", leading=1.5)

    img.save(os.path.join(OUT, "fig4_02_avant.png"))


# ---------------------------------------------------------------- FIG 4.02
def fig_after():
    W, H = 1700, 1000
    img, d = canvas(W, H, "Figure 4.03 — Topologie APRÈS SASE : un PoP unique, sept fonctions traversées par la requête",
                    "Le tunnel n'ouvre que le PoP (10.20.0.0/24) ; l'accès aux applications est décidé par l'identité.")

    # users left
    box(d, 50, 190, 235, 92, BLUE_F, BLUE, "Home laptop\n10.100.0.11", 22)
    box(d, 50, 310, 235, 92, BLUE_F, BLUE, "Mobile\n10.100.0.12", 22)
    box(d, 50, 430, 235, 108, GREEN_F, GREEN, "Succursale\nedge + branch-pc\n192.168.10.0/24", 21)

    # PoP enclosure
    d.rounded_rectangle([340, 145, 1340, 905], radius=22, fill="#FFFBEB", outline=AMBER, width=4)
    text_block(d, 360, 158, 950, "POINT DE PRÉSENCE SASE (une VM Ubuntu 24.04, 3 Go de RAM, Docker)", 24, AMBER, bold=True)
    text_block(d, 360, 194, 950, "Plan de données, plan de contrôle et plan de visibilité sur une pile réseau partagée (10.20.0.1)",
               18, MUTED)

    funcs = [
        ("A — Entrée sécurisée", "WireGuard wg0 / wg-b1 / wg-b2 — clé publique par appareil", BLUE, BLUE_F),
        ("B — FWaaS", "nftables, table inet sase_fw — INPUT / FORWARD / OUTPUT deny-by-default", SLATE, SLATE_F),
        ("C — DNS filtrant + SWG", "dnsmasq :53 (sinkhole) + Squid :3128 — ACL domaine / URL / extension", GREEN, GREEN_F),
        ("D — IAM + ZTNA", "Keycloak :8443 (OIDC, TOTP) + Pomerium :443 — politique par groupe", PURPLE, PURPLE_F),
        ("E — CASB + DLP", "mitmproxy 127.0.0.1:8081 — règles par action + moteur DLP", RED, RED_F),
    ]
    y = 235
    for i, (t, s2, c, f) in enumerate(funcs):
        box(d, 375, y, 470, 86, f, c, "", 21)
        text_block(d, 392, y + 9, 436, t, 20, c, bold=True)
        text_block(d, 392, y + 38, 436, s2, 17, INK, leading=1.2)
        if i < len(funcs) - 1:
            arrow(d, (610, y + 86), (610, y + 108), MUTED, 3)
        y += 108

    # destinations right
    d.rounded_rectangle([980, 235, 1310, 520], radius=16, fill=GREEN_F, outline=GREEN, width=3)
    text_block(d, 996, 248, 298, "Réseau apps 10.30.0.0/24\ninterne, sans Internet", 20, GREEN, bold=True)
    box(d, 998, 310, 294, 60, WHITE, GREEN, "CloudDrive (SaaS test) 10.30.0.21", 18)
    box(d, 998, 382, 294, 60, WHITE, GREEN, "Finance (ERP) 10.30.0.22", 18)
    box(d, 998, 454, 294, 60, WHITE, GREEN, "Admin IT 10.30.0.23", 18)

    box(d, 980, 610, 330, 96, BLUE_F, BLUE, "Internet simulée / réelle\nnews, casino, malware, phishing", 19)

    # E -> apps (elbow)
    d.line([(845, 721), (930, 721)], fill=RED, width=4)
    d.line([(930, 721), (930, 490)], fill=RED, width=4)
    arrow(d, (930, 490), (980, 490), RED, 4)

    # C -> Internet (elbow)
    d.line([(845, 491), (885, 491)], fill=GREEN, width=4)
    d.line([(885, 491), (885, 658)], fill=GREEN, width=4)
    arrow(d, (885, 658), (980, 658), GREEN, 4)

    # légende des deux flux (placée entre les applications et Internet)
    d.line([(998, 556), (1042, 556)], fill=GREEN, width=4)
    text_block(d, 1054, 545, 268, "Flux web : Squid -> Internet", 14, GREEN, bold=True)
    d.line([(998, 586), (1042, 586)], fill=RED, width=4)
    text_block(d, 1054, 575, 268, "Flux applicatif : CASB -> apps", 14, RED, bold=True)

    # supervision bar
    d.rounded_rectangle([375, 795, 1310, 868], radius=12, fill="#EEF2FF", outline="#4338CA", width=2)
    text_block(d, 392, 803, 900, "F — Supervision : Fluent Bit -> Loki :3100 -> Grafana", 19, "#3730A3", bold=True)
    text_block(d, 392, 831, 900, "sept sources étiquetées : firewall, dns, squid, casb, sdwan, ztna, iam", 17, "#3730A3")

    # links users -> pop
    arrow(d, (285, 236), (375, 262), BLUE, 4)
    arrow(d, (285, 356), (375, 366), BLUE, 4)
    arrow(d, (285, 484), (340, 484), GREEN, 4)
    text_block(d, 45, 575, 250, "Entrées du PoP :\nUDP 51820 (utilisateurs)\nUDP 51821/51822 (succursale)", 15, MUTED, leading=1.25)

    text_block(d, 360, 918, 940, "Aucune route vers 10.30.0.0/24 dans les profils clients : le transit direct est refusé (FORWARD drop).",
               18, RED, bold=True)

    img.save(os.path.join(OUT, "fig4_03_apres.png"))


# ---------------------------------------------------------------- FIG 4.03
def fig_virtual():
    W, H = 1700, 1000
    img, d = canvas(W, H, "Figure 4.04 — Topologie physique et virtuelle de la maquette",
                    "Hôte Windows 8 Go + VirtualBox 7.x ; une VM Ubuntu 24.04 (3 Go, 2 vCPU) et cinq réseaux Docker.")

    # host
    d.rounded_rectangle([45, 120, 430, 930], radius=18, fill="#F8FAFC", outline=SLATE, width=3)
    text_block(d, 65, 136, 340, "HÔTE WINDOWS 10/11 — 8 Go", 23, SLATE, bold=True)
    box(d, 75, 195, 325, 92, BLUE_F, BLUE, "Client WireGuard for Windows\nhome-laptop / mobile", 21)
    box(d, 75, 310, 325, 92, WHITE, BLUE, "Navigateur Edge/Chrome\nprofil dédié + proxy 10.20.0.1:3128", 20)
    box(d, 75, 425, 325, 76, WHITE, SLATE, "VirtualBox 7.x\nhyperviseur de type 2", 21)
    text_block(d, 75, 530, 325, "Réseau host-only VirtualBox\n192.168.56.0/24\nhôte .1 — DHCP désactivé", 20, MUTED)
    text_block(d, 75, 650, 325, "Réseau NAT VirtualBox\n10.0.2.0/24 — VM .15\naccès Internet de la VM", 20, MUTED)
    text_block(d, 75, 780, 325, "Point d'entrée publié :\nUDP 51820 uniquement", 21, RED, bold=True)

    # VM
    d.rounded_rectangle([500, 120, 1655, 930], radius=18, fill="#FFFBEB", outline=AMBER, width=3)
    text_block(d, 522, 136, 1080, "VM UBUNTU SERVER 24.04 « sase-pop » — 3 Go / 2 vCPU — Docker Engine", 23, AMBER, bold=True)
    box(d, 530, 190, 330, 92, WHITE, AMBER, "enp0s8 (host-only)\n192.168.56.10/24", 21)
    box(d, 530, 300, 330, 92, WHITE, AMBER, "enp0s3 (NAT)\n10.0.2.15/24", 21)
    arrow(d, (475, 220), (530, 235), BLUE, 4, "host-only", 18, ly=-24)


    # docker networks inside VM
    d.rounded_rectangle([900, 190, 1630, 910], radius=16, fill="#FFFFFF", outline="#D1D5DB", width=2)
    text_block(d, 920, 202, 690, "Réseaux Docker (sous-réseaux fixes)", 21, INK, bold=True)
    nets = [
        ("svc — 10.20.0.0/24", "pop-gw .1 | Grafana .60 | Loki .61 | Fluent Bit .62 | inet-sim .70", BLUE, BLUE_F),
        ("apps — 10.30.0.0/24 (internal)", "pop-gw .1 | CloudDrive .21 | Finance .22 | Admin .23", GREEN, GREEN_F),
        ("wan1 — 10.10.1.0/24 (internal)", "pop-gw .1 | branch-edge .2", PURPLE, PURPLE_F),
        ("wan2 — 10.10.2.0/24 (internal)", "pop-gw .1 | branch-edge .2", PURPLE, PURPLE_F),
        ("branch_lan — 192.168.10.0/24", "branch-edge .1 | branch-pc .10", AMBER, AMBER_F),
    ]
    y = 245
    for t, s, c, f in nets:
        box(d, 925, y, 680, 78, f, c, "", 20)
        text_block(d, 942, y + 8, 646, t, 19, c, bold=True)
        text_block(d, 942, y + 38, 646, s, 17, INK)
        y += 92

    # pop-gw node
    d.rounded_rectangle([925, 720, 1605, 890], radius=14, fill="#FEF2F2", outline=RED, width=3)
    text_block(d, 942, 732, 640, "pop-gw — pile réseau partagée du PoP", 20, RED, bold=True)
    text_block(d, 942, 764, 640,
               "interfaces wg0 10.100.0.1 | wg-b1 172.16.1.1 | wg-b2 172.16.2.1\n"
               "svc .1 | apps .1 | wan1 .1 | wan2 .1\n"
               "nftables, dnsmasq, Squid, Keycloak, Pomerium, mitmproxy", 18, INK)

    # branch arrow
    box(d, 530, 750, 330, 140, GREEN_F, GREEN, "branch-edge (rattaché à wan1, wan2\net branch_lan)\nLAN .1 | WAN .2 | wg-b 172.16.x.2\nbranch-pc 192.168.10.10", 18)
    arrow(d, (860, 820), (925, 820), GREEN, 4)

    # réglages de la machine virtuelle (zone libre à gauche de la pile Docker)
    box(d, 530, 455, 330, 180, WHITE, MUTED,
        "Réglages de la VM\n3 072 Mo · 2 vCPU · disque 25 Go\nswap 2 Go\n"
        "net.ipv4.ip_forward=1\nnet.netfilter.nf_log_all_netns=1", 17)

    img.save(os.path.join(OUT, "fig4_04_virtuelle.png"))


# ---------------------------------------------------------------- FIG 4.04
def fig_steps():
    W, H = 1700, 780
    img, d = canvas(W, H, "Figure 4.01 — Démarche de réalisation en onze étapes (0 à 10)",
                    "Chaque étape se termine par une vérification concluante avant de passer à la suivante.")

    lanes = [
        ("SOCLE", 160, [
            ("0", "Hôte Windows\nVirtualBox, réseau host-only"),
            ("1", "VM Ubuntu 24.04\n3 Go, 2 vCPU, IP fixe"),
            ("2", "Socle logiciel\nDocker, WireGuard, sysctl"),
            ("3", "Initialisation\nPKI, secrets, clés WireGuard"),
        ], 4),
        ("POINT DE PRÉSENCE", 340, [
            ("4a", "pop-gw\nWireGuard + nftables"),
            ("4b", "IAM + ZTNA\nKeycloak, Pomerium"),
            ("4c", "SWG + DNS\nSquid, dnsmasq"),
            ("4d", "CASB + DLP\nmitmproxy, policy.json"),
            ("4e", "SD-WAN\n2 tunnels, 3 classes"),
            ("4f", "Supervision\nFluent Bit, Loki, Grafana"),
        ], 6),
        ("MISE EN SERVICE", 560, [
            ("5-6", "Démarrage ordonné\net vérifications du PoP"),
            ("7-8", "Clients\ndistant + succursale"),
            ("9", "Première connexion\nOIDC + TOTP + CASB"),
            ("10", "Sécurisation\nexposition, secrets, privilèges"),
        ], 4),
    ]

    for lane_name, y, items, n in lanes:
        d.rounded_rectangle([35, y - 18, 1680, y + 132], radius=14, fill="#F8FAFC", outline="#CBD5E1", width=2)
        text_block(d, 52, y + 6, 130, lane_name, 19, MUTED, bold=True)
        x0, x1 = 200, 1650
        gap = 26 if n > 4 else 40
        bw = (x1 - x0 - gap * (n - 1)) / n
        for i, (num, lab) in enumerate(items):
            x = x0 + i * (bw + gap)
            fill = "#EEF2FF" if num not in ("9", "10") else "#F0FDF4"
            stroke = "#4338CA" if num not in ("9", "10") else GREEN
            box(d, x, y, bw, 112, fill, stroke, "", 18)
            d.ellipse([x + 12, y + 16, x + 62, y + 66], fill=stroke)
            f = font(21, True)
            tw = d.textlength(num, font=f)
            d.text((x + 37 - tw / 2, y + 24), num, font=f, fill=WHITE)
            text_block(d, x + 72, y + 18, bw - 82, lab, 17, INK, leading=1.2)
            if i < n - 1:
                arrow(d, (x + bw, y + 56), (x + bw + gap - 4, y + 56), MUTED, 3)
        if lane_name != "MISE EN SERVICE":
            arrow(d, (90, y + 132), (90, y + 162), MUTED, 3)
            text_block(d, 100, y + 136, 120, "puis", 15, MUTED)

    img.save(os.path.join(OUT, "fig4_01_etapes.png"))


if __name__ == "__main__":
    fig_before()
    fig_after()
    fig_virtual()
    fig_steps()
    for f in sorted(os.listdir(OUT)):
        print(f, os.path.getsize(os.path.join(OUT, f)))
