# CHAPITRE 4 : RÉALISATION TECHNIQUE ET DÉPLOIEMENT DE LA SOLUTION SASE

## 4.1 Introduction

Ce chapitre présente la réalisation technique complète de la solution SASE que j'ai conçue, déployée et validée. Contrairement à un simple guide d'installation, ce chapitre documente **mes choix d'architecture, mes décisions techniques, mon travail d'intégration et les résultats obtenus**.

Les chapitres précédents ont établi le cadre théorique : l'état de l'art des architectures d'accès distant (Chapitre 1), les composants SASE et leur convergence (Chapitre 2), puis la modélisation mathématique du comportement du système (Chapitre 3). Ce chapitre démontre que ces concepts peuvent être traduits en une architecture réelle, mesurable et validable.

### 4.1.1 Objectifs de la réalisation

Mon objectif principal était de **concevoir, implémenter et valider une architecture SASE fonctionnelle** capable de sécuriser l'accès d'utilisateurs distants aux applications cloud d'entreprise, tout en respectant une contrainte matérielle stricte : un ordinateur portable de 8 Go de RAM.

Les objectifs spécifiques sont :

1. **Authentification centralisée avec MFA** : implémenter OIDC avec Keycloak et imposer le second facteur (TOTP)
2. **Zero Trust Network Access** : aucune confiance implicite au réseau, autorisation par identité et par ressource
3. **Inspection et filtrage du trafic** : FWaaS avec nftables, SWG avec Squid, filtrage DNS
4. **Contrôle des applications SaaS** : CASB pour contrôler les actions, DLP pour détecter les données sensibles
5. **SD-WAN avec mesure de qualité** : multi-chemins avec bascule automatique basée sur le SLA
6. **Supervision centralisée** : journalisation unifiée de toutes les décisions de sécurité

### 4.1.2 Contraintes et défis techniques

La contrainte matérielle de 8 Go de RAM a structuré toutes mes décisions d'architecture. Windows 10 en consomme déjà 3 à 4 Go, laissant environ 4 Go pour l'hyperviseur, la maquette et les outils de test. Cette contrainte a trois conséquences majeures :

**Impossibilité d'une architecture multi-VM classique**
Une approche traditionnelle avec des appliances dédiées (pfSense/OPNsense pour le pare-feu : 1-2 Go, un contrôleur SD-WAN : 1-2 Go, un SIEM comme Wazuh : 2-4 Go) dépasserait immédiatement le budget mémoire.

**Nécessité d'une intégration serrée**
J'ai dû concevoir une architecture où tous les services partagent une pile réseau commune dans une seule VM de 3 Go, en utilisant des conteneurs Docker pour l'isolation.

**Sélection rigoureuse des composants**
Chaque composant a été choisi pour son empreinte mémoire réduite et sa capacité d'intégration, écartant des solutions plus complètes mais trop gourmandes (Authentik : ~1.5 Go, ELK : 2-4 Go, ClamAV : >1 Go).

### 4.1.3 Approche méthodologique

Ma démarche repose sur trois principes :

**1. Conception guidée par les contraintes**
Plutôt que d'adapter une architecture existante, j'ai conçu une solution spécifique qui maximise la couverture fonctionnelle SASE sous la contrainte matérielle donnée.

**2. Validation progressive par étapes**
Chaque composant a été intégré, configuré et validé individuellement avant d'ajouter le suivant. Cette approche en 11 étapes (numérotées de 0 à 10) permet de localiser précisément les pannes.

**3. Honnêteté sur les niveaux de réalisation**
Je distingue explicitement trois niveaux :
- **N1** : fonction implémentée et testée avec preuves
- **N2** : fonction réelle mais de profondeur réduite ou complétée par simulation
- **N3** : fonction théorique ou hors périmètre

Cette honnêteté est essentielle pour une évaluation objective de la maquette.

### 4.1.4 Structure du chapitre

Le chapitre suit l'ordre chronologique de ma réalisation :

- **Section 4.2** : Architecture de référence (AVANT SASE) et ses limites
- **Section 4.3** : Architecture cible (APRÈS SASE) et topologie physique complète
- **Section 4.4** : Décisions d'architecture et choix techniques
- **Section 4.5** : Implémentation détaillée des composants clés
- **Section 4.6** : Plan d'adressage, routage et flux de sécurité
- **Section 4.7** : Déploiement et intégration
- **Section 4.8** : Validation fonctionnelle par scénarios
- **Section 4.9** : Métriques de performance et analyse
- **Section 4.10** : Bilan technique, limites et perspectives

---

## 4.2 Architecture de référence : la topologie AVANT SASE

### 4.2.1 Description de l'architecture traditionnelle

Avant d'introduire SASE, l'architecture de référence repose sur un modèle classique **VPN + pare-feu périmétrique** que l'on retrouve dans de nombreuses entreprises. Cette architecture, illustrée dans la Figure 4.01, présente cinq composants principaux :

**Figure 4.01 : Architecture réseau traditionnelle AVANT SASE**

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INTERNET                                    │
└────────┬────────────────────────────────────────────┬────────────────┘
         │                                            │
         │                                            │
    ┌────▼────────────────┐                    ┌─────▼──────────────┐
    │  Utilisateur        │                    │  Succursale        │
    │  Distant            │                    │  (Bureau)          │
    │  (Domicile/Mobile)  │                    │                    │
    └────┬────────────────┘                    └─────┬──────────────┘
         │                                            │
         │ Tunnel VPN IPsec/SSL                       │ Lien WAN unique
         │ (accès complet au réseau interne)          │
         │                                            │
         └─────────────┬──────────────────────────────┘
                       │
              ┌────────▼─────────────┐
              │  Concentrateur VPN   │
              │  + Pare-feu          │
              │  Périmétrique        │
              │  (Filtrage par IP)   │
              └────────┬─────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
    ┌────▼─────────┐        ┌───────▼────────┐
    │ Réseau       │        │  Applications  │
    │ Interne      │        │  SaaS Cloud    │
    │ (LAN à plat) │        │  (sans contrôle)│
    └──────────────┘        └────────────────┘
         │                           │
         │ Backhaul Internet         │ Accès direct
         └───────────────────────────┘
```

#### Composants de l'architecture traditionnelle

**1. Concentrateur VPN**
- Authentifie l'utilisateur (généralement via Active Directory)
- Établit un tunnel chiffré (IPsec ou SSL VPN)
- Attribue une adresse IP dans le réseau interne
- **Problème** : une fois authentifié, l'utilisateur a accès à tout le réseau

**2. Pare-feu périmétrique**
- Filtre le trafic entrant/sortant par adresse IP source/destination et ports
- Applique des règles de segmentation par VLAN
- **Problème** : ne connaît pas l'identité de l'utilisateur, seulement son adresse IP

**3. Réseau interne à plat**
- Les serveurs et applications sont accessibles directement par IP
- Segmentation limitée par VLAN
- **Problème** : mouvement latéral facile en cas de compromission

**4. Accès aux applications SaaS**
- Soit direct depuis l'utilisateur (contourne la sécurité de l'entreprise)
- Soit via backhaul : le trafic revient au siège, traverse le pare-feu, puis repart vers Internet
- **Problème** : latence élevée, aucun contrôle des actions dans l'application

**5. Succursale avec lien unique**
- Un seul lien WAN vers le siège
- Pas de mesure de qualité ni de redondance
- **Problème** : single point of failure

### 4.2.2 Topologie physique détaillée de l'architecture traditionnelle

Pour comprendre précisément ce qui change avec SASE, j'ai modélisé l'architecture traditionnelle avec les mêmes composants que ma maquette : un utilisateur distant, une succursale, des applications internes et des services cloud.

**Tableau 4.01 : Caractéristiques techniques de l'architecture traditionnelle**

| Couche | Composant | Adressage | Contrôle de sécurité |
|--------|-----------|-----------|----------------------|
| **Accès distant** | VPN IPsec/SSL | 10.0.0.0/8 (réseau privé complet) | Authentification par certificat ou mot de passe |
| **Périmètre** | Pare-feu Firewall | VLAN 10, 20, 30 | ACL par IP source/destination |
| **Réseau interne** | Switch L2/L3 | 192.168.0.0/16 | Segmentation VLAN limitée |
| **Applications** | Serveurs internes | 192.168.10.0/24 | Aucun contrôle d'accès applicatif |
| **SaaS Cloud** | Office 365, Salesforce, etc. | Internet public | Aucun contrôle côté entreprise |
| **Succursale** | Routeur + Firewall | 10.1.0.0/16 | Tunnel site-to-site IPsec |

#### Flux typique d'une connexion utilisateur distant (architecture traditionnelle)

```
1. Utilisateur distant → Concentrateur VPN (port UDP 500 IPsec ou TCP 443 SSL VPN)
   ✓ Authentification : username/password + certificat
   ✓ Établissement du tunnel chiffré
   
2. Attribution d'une adresse IP interne : 10.0.100.x
   ⚠️ L'utilisateur appartient maintenant au réseau interne
   
3. Accès à un serveur interne : 192.168.10.5
   → Traverse le pare-feu périmétrique
   → Règle : ALLOW src 10.0.100.0/24 dst 192.168.10.0/24 tcp/any
   ⚠️ Aucune vérification de l'identité de l'utilisateur spécifique
   ⚠️ Aucun contrôle de l'application ou de l'action
   
4. Accès à Office 365 (SaaS)
   Scénario A (accès direct) : 
   → Utilisateur → Internet → Office 365
   ⚠️ Contourne complètement la sécurité de l'entreprise
   
   Scénario B (backhaul) :
   → Utilisateur → VPN → Réseau interne → Proxy → Internet → Office 365
   ⚠️ Latence élevée, bande passante gaspillée
   ⚠️ Aucun contrôle des actions dans Office 365
```

### 4.2.3 Limites techniques identifiées

Mon analyse de cette architecture révèle **neuf limites majeures** qui justifient la migration vers SASE :

#### L1 : Confiance implicite post-authentification
**Problème** : Une fois le tunnel VPN établi, l'utilisateur est "dans" le réseau interne et bénéficie d'une confiance implicite. Un appareil compromis obtient le même accès.

**Impact mesuré** : Dans ma maquette de référence, un utilisateur authentifié peut scanner tous les ports du réseau 10.30.0.0/24 (applications) sans restriction.

#### L2 : Contrôle par adresse IP, pas par identité
**Problème** : Le pare-feu filtre par adresse IP source/destination. Si plusieurs utilisateurs partagent le même pool DHCP VPN (10.0.100.0/24), ils ont les mêmes droits.

**Impact** : Impossible de différencier alice (du département Finance) de bob (IT Admin) au niveau réseau.

#### L3 : Absence de contrôle applicatif
**Problème** : Le pare-feu autorise le port TCP 80/443, mais ne peut pas distinguer une lecture d'un téléversement dans une application web.

**Impact** : Aucun moyen d'autoriser la consultation d'un document tout en interdisant son téléchargement ou son partage.

#### L4 : Backhaul inefficace pour le SaaS
**Problème** : Le trafic vers Office 365 ou Salesforce doit revenir au siège, traverser le proxy/pare-feu, puis repartir vers Internet.

**Impact mesuré** : 
- Latence additionnelle : +80-150 ms (VPN utilisateur → siège → Internet vs accès direct)
- Bande passante siège saturée par le trafic cloud des utilisateurs distants

#### L5 : Aucune visibilité ni contrôle des applications SaaS
**Problème** : L'entreprise ne voit pas ce qui se passe dans les applications cloud. Un utilisateur peut partager un document confidentiel publiquement sans détection.

**Impact** : Risque de fuite de données, Shadow IT incontrôlé.

#### L6 : Politiques de sécurité fragmentées
**Problème** : Chaque équipement (VPN, firewall, proxy, switch) a sa propre console et son propre format de politique.

**Impact opérationnel** : 
- Temps de déploiement d'une nouvelle règle : ~30-60 minutes (accès à 3-4 consoles différentes)
- Risque d'incohérence entre les équipements

#### L7 : Journalisation dispersée
**Problème** : Les logs du VPN sont dans un fichier, ceux du firewall dans un autre, ceux du proxy ailleurs.

**Impact** : En cas d'incident de sécurité, impossible de reconstituer rapidement le parcours d'un utilisateur à travers les systèmes.

#### L8 : Succursale avec lien unique, sans mesure
**Problème** : Un seul lien WAN entre la succursale et le siège. Aucune mesure de qualité (latence, perte de paquets).

**Impact** :
- En cas de panne : perte de connectivité complète
- En cas de dégradation : aucune détection automatique, pas de bascule

#### L9 : Absence de segmentation au niveau utilisateur
**Problème** : La segmentation VLAN protège les serveurs entre eux, mais pas les accès utilisateurs.

**Impact** : Un utilisateur du département Finance peut accéder aux serveurs IT s'il connaît leur adresse IP.

### 4.2.4 Synthèse : pourquoi SASE est nécessaire

Le tableau 4.02 synthétise les limitations de l'architecture traditionnelle et les exigences qui en découlent pour l'architecture SASE.

**Tableau 4.02 : Limitations de l'architecture traditionnelle et exigences SASE**

| Limitation | Conséquence sécurité | Exigence pour SASE |
|------------|---------------------|-------------------|
| Confiance implicite réseau | Mouvement latéral facilité | Zero Trust : vérification continue |
| Contrôle par IP, pas identité | Impossible de personnaliser les droits | Politique par identité et groupe |
| Pas de contrôle applicatif | Fuite de données via SaaS | CASB + DLP en ligne |
| Backhaul inefficace | Latence élevée, bande passante gaspillée | Inspection locale au PoP |
| Logs fragmentés | Investigation longue | Journalisation centralisée |
| Lien unique | Pas de résilience | SD-WAN multi-chemins |
| Politiques dispersées | Erreurs de configuration | Contrôle centralisé |

Cette analyse démontre que l'architecture traditionnelle est inadaptée à trois évolutions majeures :
1. **Le cloud-first** : les applications ne sont plus dans le datacenter
2. **Le travail distribué** : les utilisateurs ne sont plus au bureau
3. **Le Zero Trust** : le réseau interne n'est plus un périmètre de confiance

La section suivante présente l'architecture SASE que j'ai conçue pour répondre à ces limitations.

---

## 4.3 Architecture cible : la topologie APRÈS SASE

### 4.3.1 Principe de l'architecture SASE réalisée

L'architecture SASE que j'ai implémentée repose sur un **changement de paradigme** : au lieu de donner accès au réseau puis de filtrer, elle n'ouvre l'accès qu'au Point de Présence (PoP), qui décide ensuite de chaque accès applicatif selon l'identité.

**Principes directeurs de ma conception :**

1. **Un seul point d'entrée** : le PoP SASE (10.20.0.0/24), pas le réseau applicatif
2. **Authentification forte** : OIDC avec MFA (TOTP) obligatoire
3. **Autorisation par ressource** : chaque application a sa propre politique (identité + groupes)
4. **Convergence des fonctions** : FWaaS, ZTNA, SWG, CASB, DLP, SD-WAN dans le même nœud
5. **Visibilité complète** : tous les composants journalisent dans Loki/Grafana

### 4.3.2 Vue d'ensemble de la topologie physique APRÈS SASE

La Figure 4.02 présente la topologie complète de mon architecture SASE.

**Figure 4.02 : Topologie physique et logique de l'architecture SASE réalisée**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET RÉEL                                    │
│                         (Accès VM pour téléchargements)                       │
└────────────────────┬─────────────────────────────────────────────────────────┘
                     │
                     │ NAT VirtualBox
                     │ 10.0.2.0/24
                     │
┌────────────────────▼──────────────────────────────────────────────────────────┐
│                        HÔTE WINDOWS 10 - Dell Latitude 3500                   │
│                      CPU: Intel i5-8265U (1.6 GHz, 8 vCPU)                    │
│                              RAM: 8 Go (3-4 Go utilisés)                      │
│                                                                                │
│  ┌───────────────────────────────────────────────────────────────────┐       │
│  │                  VirtualBox Hypervisor                            │       │
│  │                                                                    │       │
│  │   ┌────────────────────────────────────────────────────────┐     │       │
│  │   │        Machine Virtuelle "sase-pop"                    │     │       │
│  │   │        Ubuntu Server 24.04 LTS - 3 Go RAM             │     │       │
│  │   │                                                         │     │       │
│  │   │  Interface enp0s8: 192.168.56.10/24 (Host-Only)       │     │       │
│  │   │  ↑ Point d'entrée PUBLIC du PoP SASE                  │     │       │
│  │   │  │ UDP 51820, 51821, 51822 : WireGuard                │     │       │
│  │   │  │                                                      │     │       │
│  │   │  Interface enp0s3: 10.0.2.15 (NAT) → Internet         │     │       │
│  │   │                                                         │     │       │
│  │   │  ┌────────────────────────────────────────────┐       │     │       │
│  │   │  │      CONTENEUR pop-gw (Debian 12)          │       │     │       │
│  │   │  │      LE CŒUR DU PoP SASE                   │       │     │       │
│  │   │  │                                             │       │     │       │
│  │   │  │  ┌─ wg0: 10.100.0.1/24 ─────────────┐     │       │     │       │
│  │   │  │  │   Overlay utilisateurs distants   │     │       │     │       │
│  │   │  │  │   ├─ home-laptop: .11            │     │       │     │       │
│  │   │  │  │   └─ mobile: .12                 │     │       │     │       │
│  │   │  │  │                                    │     │       │     │       │
│  │   │  │  ┌─ wg-b1: 172.16.1.1/30 ────────┐  │     │       │     │       │
│  │   │  │  │   Tunnel SD-WAN succursale #1  │  │     │       │     │       │
│  │   │  │  │   (lien business via wan1)     │  │     │       │     │       │
│  │   │  │  │                                 │  │     │       │     │       │
│  │   │  │  ┌─ wg-b2: 172.16.2.1/30 ────────┐│  │     │       │     │       │
│  │   │  │  │   Tunnel SD-WAN succursale #2 ││  │     │       │     │       │
│  │   │  │  │   (lien bulk via wan2)        ││  │     │       │     │       │
│  │   │  │  │                                ││  │     │       │     │       │
│  │   │  │  └─ nftables (FWaaS) ────────────┘│  │     │       │     │       │
│  │   │  │     - INPUT: deny-by-default      │  │     │       │     │       │
│  │   │  │     - FORWARD: deny-by-default    │  │     │       │     │       │
│  │   │  │     - OUTPUT: web/DNS only        │  │     │       │     │       │
│  │   │  │                                    │  │     │       │     │       │
│  │   │  │  └─ Agent SD-WAN PoP (SLA)       │  │     │       │     │       │
│  │   │  │     - Mesure RTT et perte         │  │     │       │     │       │
│  │   │  │     - Route de retour dynamique   │  │     │       │     │       │
│  │   │  └────────────────────────────────────┘  │     │       │     │       │
│  │   │                 │                         │     │       │     │       │
│  │   │  ┌──────────────┴────────┬───────────────┴─────┬───────┴────┐│       │
│  │   │  │                       │                     │            ││       │
│  │   │  │ Réseau "svc"          │ Réseau "apps"       │ wan1/wan2  ││       │
│  │   │  │ 10.20.0.0/24          │ 10.30.0.0/24        │ Simulés    ││       │
│  │   │  │                       │ (Interne seulement) │            ││       │
│  │   │  │                       │                     │            ││       │
│  │   │ ┌▼──────────────┐ ┌─────▼─────────┐  ┌────────▼────────┐   ││       │
│  │   │ │ Keycloak      │ │ CloudDrive    │  │ branch-edge     │   ││       │
│  │   │ │ (.1:8443)     │ │ (.21:5000)    │  │ (.2 sur wan1/2) │   ││       │
│  │   │ │               │ │               │  │                 │   ││       │
│  │   │ │ IAM + MFA     │ │ App SaaS Test │  │ - 2x WireGuard  │   ││       │
│  │   │ │ TOTP          │ │ (Protected by │  │ - nftables      │   ││       │
│  │   │ │ Royaume:sase  │ │ CASB/DLP)     │  │ - ip rule       │   ││       │
│  │   │ └───────────────┘ │               │  │ - Agent SD-WAN  │   ││       │
│  │   │                   └───────────────┘  │ - impair (netem)│   ││       │
│  │   │ ┌─────────────────┐ ┌──────────────┐└─────────────────┘   ││       │
│  │   │ │ Pomerium        │ │ Finance      │         │             ││       │
│  │   │ │ (.1:443)        │ │ (.22:80)     │         │             ││       │
│  │   │ │                 │ │              │         │             ││       │
│  │   │ │ ZTNA Proxy      │ │ App privée   │    ┌────▼────────┐   ││       │
│  │   │ │ Routes + ACL    │ │ (Groupe      │    │ branch-pc   │   ││       │
│  │   │ │ par groupe      │ │ finance only)│    │(.10)        │   ││       │
│  │   │ └─────────────────┘ └──────────────┘    │             │   ││       │
│  │   │                                          │ LAN 192.168 │   ││       │
│  │   │ ┌─────────────────┐ ┌──────────────┐   │ .10.0/24    │   ││       │
│  │   │ │ mitmproxy       │ │ Admin        │    └─────────────┘   ││       │
│  │   │ │ (.1:8081)       │ │ (.23:80)     │                      ││       │
│  │   │ │                 │ │              │                      ││       │
│  │   │ │ CASB + DLP      │ │ App privée   │                      ││       │
│  │   │ │ Reverse Proxy   │ │ (Groupe      │                      ││       │
│  │   │ │ Policy.json     │ │ it-admin)    │                      ││       │
│  │   │ └─────────────────┘ └──────────────┘                      ││       │
│  │   │                                                            ││       │
│  │   │ ┌─────────────────┐ ┌──────────────┐                     ││       │
│  │   │ │ Squid           │ │ inet-sim     │                     ││       │
│  │   │ │ (.1:3128)       │ │ (.70:80)     │                     ││       │
│  │   │ │                 │ │              │                     ││       │
│  │   │ │ SWG Proxy       │ │ Internet     │                     ││       │
│  │   │ │ ACL + blocklist │ │ Simulé       │                     ││       │
│  │   │ └─────────────────┘ └──────────────┘                     ││       │
│  │   │                                                            ││       │
│  │   │ ┌─────────────────┐ ┌──────────────┐ ┌──────────────┐  ││       │
│  │   │ │ dnsmasq         │ │ Loki         │ │ Grafana      │  ││       │
│  │   │ │ (.1:53)         │ │ (.61:3100)   │ │ (.60:3000)   │  ││       │
│  │   │ │                 │ │              │ │              │  ││       │
│  │   │ │ DNS + Sinkhole  │ │ Log Storage  │ │ Visualisation│  ││       │
│  │   │ │ Filtrage        │ │              │ │ (via ZTNA)   │  ││       │
│  │   │ └─────────────────┘ └──────────────┘ └──────────────┘  ││       │
│  │   │                          ▲                               ││       │
│  │   │                          │                               ││       │
│  │   │                   ┌──────┴──────┐                       ││       │
│  │   │                   │ Fluent Bit  │                       ││       │
│  │   │                   │ (.62:24224) │                       ││       │
│  │   │                   │             │                       ││       │
│  │   │                   │ Log         │                       ││       │
│  │   │                   │ Collector   │                       ││       │
│  │   │                   └─────────────┘                       ││       │
│  │   └────────────────────────────────────────────────────────┘│       │
│  └────────────────────────────────────────────────────────────────     │
│                                                                         │
│  ┌────────────────────────────────────────────────┐                    │
│  │  Client WireGuard (Windows)                    │                    │
│  │  - Tunnel: home-laptop.conf                    │                    │
│  │  - IP overlay: 10.100.0.11                     │                    │
│  │  - Endpoint: 192.168.56.10:51820               │                    │
│  │  - DNS: 10.100.0.1 (dnsmasq du PoP)           │                    │
│  │  - Routes: 10.20.0.0/24, 10.100.0.1/32 seulem│                    │
│  │                                                 │                    │
│  │  Navigateur Edge (profil dédié):               │                    │
│  │  - Proxy: http://10.20.0.1:3128               │                    │
│  │  - Bypass: *.sase.lab (accès direct ZTNA)    │                    │
│  │  - CA approuvée: sase-lab-ca.crt              │                    │
│  └────────────────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘

LÉGENDE:
━━━━  Flux de données applicatif
┄┄┄┄  Flux de contrôle/gestion
═══   Tunnel WireGuard chiffré
```

### 4.3.3 Composants de l'architecture SASE et leur rôle technique

Le tableau 4.03 détaille chaque composant de mon architecture, son rôle dans SASE, et les choix techniques que j'ai effectués.

**Tableau 4.03 : Composants SASE implémentés et justification technique**

| Composant | Composante SASE | Image/Version | RAM | Justification technique |
|-----------|----------------|---------------|-----|------------------------|
| **pop-gw** | Point de Présence | Debian 12 custom | ~50 Mo | Noyau du PoP, héberge WireGuard (noyau Linux), nftables, agent SD-WAN, iperf3. Seul conteneur avec NET_ADMIN. |
| **Keycloak** | IAM + MFA | quay.io/keycloak/keycloak:26.0 | 600-800 Mo | Fournisseur OIDC avec MFA TOTP natif, mapper de groupes, journal d'événements. Tas Java plafonné à 640 Mo (-Xmx640m). |
| **Pomerium** | ZTNA | pomerium/pomerium:latest | 100-200 Mo | Proxy d'accès Zero Trust sans agent pour HTTP(S). Politique déclarative par route avec support OIDC natif. Alternative légère à Authentik/Zitadel. |
| **mitmproxy** | CASB + DLP | mitmproxy/mitmproxy:10.x | 100-150 Mo | Reverse proxy programmable (Python). Seul outil capable d'inspecter le corps des requêtes HTTP et d'extraire le JWT pour les règles CASB. |
| **Squid** | SWG | ubuntu/squid:latest | 40-80 Mo | Proxy web explicite, ACL par domaine/URL/extension. Pas de cache (cache_mem 8 MB only) pour réduire la mémoire. |
| **dnsmasq** | Filtrage DNS | Intégré dans pop-gw | <10 Mo | Résolveur DNS léger avec support de sinkhole (0.0.0.0). Résout les noms du lab (*.sase.lab → 10.20.0.1). |
| **Loki** | Supervision | grafana/loki:3.x | ~100 Mo | Stockage de logs par labels, sans indexation complète (alternative légère à Elasticsearch). |
| **Fluent Bit** | Collecte logs | fluent/fluent-bit:3.x | ~20 Mo | Collecteur de logs ultra-léger (vs Logstash 500+ Mo). Lit fichiers + driver Docker fluentd. |
| **Grafana** | Visualisation | grafana/grafana:11.x | ~150 Mo | Interface de supervision. Publié via Pomerium (groupe it-admin seulement). |
| **CloudDrive** | App SaaS test | Flask custom | ~30 Mo | Application de démonstration que j'ai développée en Python/Flask pour tester CASB/DLP. Affiche identité JWT. |
| **Finance/Admin** | Apps privées | nginx:alpine | ~10 Mo chacune | Pages statiques simulant des applications internes. Accès contrôlé par ZTNA. |
| **inet-sim** | Internet simulé | nginx:alpine | ~10 Mo | Serveur nginx simulant destinations internet (news.inet.lab, casino.inet.lab, etc.) pour tests SWG. |
| **branch-edge** | SD-WAN edge | Debian 12 custom | ~30 Mo | Équipement de succursale : 2x WireGuard, nftables (classification), ip rule (PBR), agent SLA, impair (netem). |
| **branch-pc** | Client branch | alpine + curl | ~10 Mo | Poste du LAN succursale pour tests. |

**Total conteneurs + OS VM : ~1.7-2.1 Go utilisés sur 3 Go alloués, marge ~900 Mo**

### 4.3.4 Décisions d'architecture majeures

#### Décision 1 : Un seul conteneur pop-gw pour la pile réseau

**Problème** : WireGuard, nftables et le routage doivent partager la même stack réseau pour que les règles de pare-feu voient les vraies adresses sources des tunnels.

**Solution adoptée** : Tous les autres conteneurs utilisent `network_mode: container:pop-gw`, c'est-à-dire qu'ils partagent la pile réseau de pop-gw.

**Avantages** :
- Les règles nftables voient les interfaces wg0, wg-b1, wg-b2
- Les ACL Squid peuvent filtrer par source 10.100.0.0/24 (clients tunnelés)
- Un seul jeu de règles iptables/nftables au lieu de NAT Docker complexe
- Logs fidèles aux adresses réelles (pas de traduction Docker)

**Inconvénient** :
- Tous les services partagent le même domaine de panne : si pop-gw crashe, tout s'arrête

**Justification** : Pour une maquette monoPoP, cette architecture simplifie considérablement le routage et le débogage. En production avec plusieurs PoP, on répartirait sur plusieurs nœuds.

#### Décision 2 : Pas d'inspection TLS généralisée (ssl_bump)

**Problème** : Sans ssl_bump de Squid, le SWG ne peut filtrer HTTPS que par nom d'hôte dans CONNECT, pas par URL ou contenu.

**Solution adoptée** : Filtrage HTTPS limité au domaine, inspection complète seulement pour CloudDrive (CASB via mitmproxy avec CA du lab).

**Justification technique** :
- ssl_bump nécessite d'installer la CA du lab sur tous les clients
- Augmente légèrement la RAM de Squid (~20-30 Mo supplémentaires)
- Pose des questions de vie privée (MITM du trafic chiffré)
- Pour la démonstration, le filtrage DNS + domaine suffit à prouver le concept SWG

**Niveau de réalisation** : N2 pour SWG (HTTP N1, HTTPS par domaine N2)

#### Décision 3 : JWT non vérifié en signature par le CASB

**Problème** : L'add-on mitmproxy décode le JWT `X-Pomerium-Jwt-Assertion` mais ne vérifie pas sa signature HMAC.

**Solution adoptée** : Acceptée pour la maquette car le port 8081 (mitmproxy) n'écoute que sur 127.0.0.1 et nftables interdit l'accès direct depuis les tunnels.

**Preuve de sécurité** :
```bash
# Depuis Windows (tunnel actif):
curl.exe -I http://10.20.0.1:8081
# Résultat: Délai dépassé (connexion refusée par nftables)

# Depuis pop-gw (même stack réseau):
docker exec pop-gw curl -I http://127.0.0.1:8081
# Résultat: HTTP/1.1 400 Bad Request (pas de JWT)
```

**Justification** : Dans un environnement de production multi-tenant, il faudrait vérifier la signature. Ici, la sécurité repose sur l'isolation réseau (nftables + Docker network).

#### Décision 4 : Contrôleur SD-WAN = fichier partagé

**Problème** : Un vrai contrôleur SD-WAN (flexiWAN, Versa, etc.) nécessite une VM dédiée (1-2 Go) et une licence.

**Solution adoptée** : Fichier `sdwan-policy.env` monté en lecture seule dans branch-edge et pop-gw. Les agents locaux prennent les décisions de routage.

**Conséquences** :
- Pas de topologie dynamique (ajout manuel de nouveaux sites)
- Pas d'interface graphique pour visualiser les métriques
- Les agents sont autonomes : décision locale basée sur SLA mesuré

**Niveau de réalisation** : N2 (SD-WAN fonctionnel mais contrôle simplifié)

#### Décision 5 : Aucune authentification au proxy Squid

**Problème** : Squid ne connaît pas l'identité de l'utilisateur, donc pas de politique web personnalisée (alice peut naviguer sur linkedin.com mais pas bob).

**Solutions envisagées** :
1. Authentification NTLM/Kerberos : nécessite Active Directory
2. Authentification par IP : peu fiable avec DHCP
3. Passer tout le web via Pomerium : complexité accrue

**Solution adoptée** : Squid filtre de manière uniforme pour tous les utilisateurs tunnelés (ACL `users src 10.100.0.0/24 192.168.10.0/24`).

**Justification** : La personnalisation par identité est démontrée au niveau ZTNA (Pomerium) et CASB (mitmproxy avec JWT). Étendre cela au proxy web aurait nécessité une intégration Squid-Keycloak complexe avec un helper external_acl_type.

**Perspective d'amélioration** : Ajouter un helper Python qui vérifie le JWT dans une en-tête HTTP personnalisée.

---

## 4.4 Plan d'adressage, routage et flux de sécurité

### 4.4.1 Plan d'adressage IP complet

Un plan d'adressage rigoureux est essentiel pour comprendre et déboguer l'architecture. Le tableau 4.04 documente tous les réseaux de ma maquette.

**Tableau 4.04 : Plan d'adressage IPv4 complet de l'architecture SASE**

| Réseau | Sous-réseau | Rôle | Équipements | Gateway | Caractéristiques |
|--------|-------------|------|-------------|---------|------------------|
| **VirtualBox Host-Only** | 192.168.56.0/24 | "Internet public" du lab | Hôte Windows: .1, VM: .10 | .1 | Interface vboxnet0, DHCP désactivé, simulate WAN |
| **VirtualBox NAT** | 10.0.2.0/24 | Accès Internet réel | VM: 10.0.2.15 | 10.0.2.2 | Pour téléchargements apt/docker, masqué |
| **wg0 overlay** | 10.100.0.0/24 | Utilisateurs distants | PoP: .1, home-laptop: .11, mobile: .12 | - | WireGuard, chiffré ChaCha20-Poly1305, MTU 1380 |
| **wg-b1 tunnel** | 172.16.1.0/30 | SD-WAN lien 1 (business) | PoP: .1, branch-edge: .2 | - | UDP 51821, préféré pour TCP 443/3128/8443/53 |
| **wg-b2 tunnel** | 172.16.2.0/30 | SD-WAN lien 2 (bulk) | PoP: .1, branch-edge: .2 | - | UDP 51822, préféré pour le reste |
| **svc (services)** | 10.20.0.0/24 | Services du PoP | pop-gw: .1, Grafana: .60, Loki: .61, Fluent Bit: .62, inet-sim: .70 | .1 | Réseau Docker bridge, accessible via tunnels |
| **apps (applications)** | 10.30.0.0/24 | Applications privées | pop-gw: .1, CloudDrive: .21, Finance: .22, Admin: .23 | .1 | Interne seulement, NO Internet, FORWARD=deny |
| **wan1 (simulé)** | 10.10.1.0/24 | Lien WAN 1 succursale | pop-gw: .1, branch-edge: .2 | - | Docker network interne, porte wg-b1 |
| **wan2 (simulé)** | 10.10.2.0/24 | Lien WAN 2 succursale | pop-gw: .1, branch-edge: .2 | - | Docker network interne, porte wg-b2 |
| **branch_lan** | 192.168.10.0/24 | LAN de la succursale | branch-edge: .1, branch-pc: .10 | .1 | Simule le réseau d'une succursale distante |

#### Adresses clés pour la compréhension :

**Point d'entrée public du PoP** : 192.168.56.10:51820 (UDP)
- C'est l'endpoint WireGuard des clients distants
- Seul port exposé à "l'Internet" du laboratoire
- nftables accepte UDP 51820 depuis ANY, 51821 depuis 10.10.1.2, 51822 depuis 10.10.2.2

**Résolution DNS interne** :
```
*.sase.lab         → 10.20.0.1 (PoP)
inet.lab           → 10.20.0.70 (Internet simulé)
malware.inet.lab   → 0.0.0.0 (sinkhole)
phishing.inet.lab  → 0.0.0.0 (sinkhole)
casino.inet.lab    → 0.0.0.0 (sinkhole)
```

**Routes WireGuard** :

Client home-laptop :
```ini
[Interface]
Address = 10.100.0.11/32
DNS = 10.100.0.1

[Peer]
PublicKey = <clé publique du PoP>
Endpoint = 192.168.56.10:51820
AllowedIPs = 10.20.0.0/24, 10.100.0.1/32   # Seulement le PoP, PAS 10.30.0.0/24 !
PersistentKeepalive = 25
```

Équipement branch-edge (tunnel wg-b1) :
```ini
[Peer]
PublicKey = <clé publique du PoP>
Endpoint = 10.10.1.1:51821
AllowedIPs = 10.20.0.0/24, 172.16.1.1/32   # Accès aux services PoP, pas aux apps
```

**Observation importante** : Les clients n'ont jamais de route vers 10.30.0.0/24. L'accès aux applications se fait exclusivement via Pomerium (proxy inverse sur 10.20.0.1:443), qui lui-même route vers 10.30.0.x selon la politique ZTNA.

### 4.4.2 Tables de routage et routage par politique (PBR)

#### Table de routage de pop-gw

```bash
$ docker exec pop-gw ip route
default via 10.0.2.2 dev eth0          # Internet (NAT VirtualBox)
10.20.0.0/24 dev eth0 scope link       # Réseau svc
10.30.0.0/24 dev eth1 scope link       # Réseau apps (interne)
10.100.0.0/24 dev wg0 scope link       # Overlay utilisateurs
172.16.1.0/30 dev wg-b1 scope link     # Tunnel SD-WAN 1
172.16.2.0/30 dev wg-b2 scope link     # Tunnel SD-WAN 2
192.168.10.0/24 via 172.16.2.2 dev wg-b2  # LAN succursale (route dynamique SD-WAN)
```

La dernière ligne est **modifiée dynamiquement par l'agent SD-WAN du PoP** :
- Si wg-b1 est optimal : `via 172.16.1.2 dev wg-b1`
- Si wg-b2 est optimal : `via 172.16.2.2 dev wg-b2`

#### Policy-Based Routing (PBR) de branch-edge

L'équipement de succursale utilise `ip rule` et `fwmark` pour router selon la classe de trafic.

```bash
$ docker exec branch-edge ip rule
0:   from all lookup local
100: from all fwmark 0x1 lookup 101   # Classe business → table 101
101: from all fwmark 0x2 lookup 102   # Classe realtime → table 102
32766: from all lookup main            # Classe bulk (défaut) → table main
32767: from all lookup default
```

```bash
$ docker exec branch-edge ip route show table 101
default via 172.16.1.1 dev wg-b1       # Classe business via tunnel 1

$ docker exec branch-edge ip route show table 102
default via 172.16.2.1 dev wg-b2       # Classe realtime via meilleur lien (variable)

$ docker exec branch-edge ip route show table main
default via 172.16.2.1 dev wg-b2       # Bulk (défaut) via tunnel 2
10.20.0.0/24 via 172.16.2.1 dev wg-b2
192.168.10.0/24 dev eth0 scope link
```

#### Classification nftables pour SD-WAN

Le marquage des paquets est effectué par nftables sur branch-edge :

```nft
table inet sdwan_classifier {
  chain output {
    type route hook output priority -150;
    
    # Classe BUSINESS : trafic critique (HTTPS, DNS, proxy Squid, Keycloak)
    tcp dport { 443, 3128, 8443 } mark set 0x1 comment "business-class"
    udp dport 53 mark set 0x1 comment "business-class-dns"
    tcp dport 53 mark set 0x1 comment "business-class-dns-tcp"
    
    # Classe REALTIME : VoIP, tests iperf
    udp dport { 5060, 5201 } mark set 0x2 comment "realtime-class"
    
    # Classe BULK : tout le reste (mark 0x0 = défaut)
    # Pas de règle explicite, mark reste à 0
  }
}
```

**Fonctionnement** :
1. Un paquet TCP/443 (HTTPS) sort de branch-pc vers Internet
2. nftables mark set 0x1 (classe business)
3. ip rule lookup 101
4. Table 101 : default via wg-b1
5. Paquet routé via tunnel wg-b1 (lien business)

**Bascule SD-WAN** :
- L'agent mesure toutes les 2s le RTT et la perte via ICMP vers 10.20.0.1
- Si wg-b1 dégradé (RTT > 120ms OU perte > 20%) :
  - L'agent modifie la table 101 : `default via 172.16.2.1 dev wg-b2`
- Classe business bascule sur wg-b2 sans coupure TCP

### 4.4.3 Flux de sécurité détaillés

Cette section documente les **chemins de paquets réels** à travers les contrôles de sécurité.

#### Flux 1 : Authentification OIDC (première connexion)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. Utilisateur ouvre https://files.sase.lab dans le navigateur      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 2. Résolution DNS                                                    │
│    Client → 10.100.0.1:53 (dnsmasq)                                 │
│    Réponse : files.sase.lab = 10.20.0.1                            │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 3. Requête HTTPS initiale                                            │
│    Client (10.100.0.11) → 10.20.0.1:443                            │
│    ├─ Paquet traverse wg0 (authentifié par clé WireGuard)          │
│    ├─ nftables INPUT : autorise (iifname wg0, tcp dport 443)       │
│    └─ Arrive à Pomerium (écoute sur 10.20.0.1:443)                 │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 4. Pomerium vérifie la session                                       │
│    Pas de cookie de session → Redirection 302                        │
│    Location: https://authenticate.sase.lab/oauth2/authorize?...     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 5. Redirection vers Keycloak                                         │
│    authenticate.sase.lab redirige vers                               │
│    https://idp.sase.lab:8443/realms/sase/protocol/openid-connect/auth│
│    ├─ Client → 10.20.0.1:8443 (Keycloak)                           │
│    └─ nftables INPUT : autorise (iifname wg0, tcp dport 8443)      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 6. Saisie des credentials                                            │
│    Utilisateur saisit : alice / Alice#Lab2026                        │
│    Keycloak vérifie dans la base H2                                  │
│    ✓ Mot de passe correct                                           │
│    ✓ Compte enabled                                                 │
│    ⚠ Action requise : CONFIGURE_TOTP (première connexion)           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 7. Configuration MFA (TOTP)                                          │
│    Keycloak affiche QR code + clé secrète                           │
│    Utilisateur scanne OU calcule le code :                           │
│    $ oathtool --totp -b <SECRET_BASE32>                             │
│    Saisie du code TOTP à 6 chiffres                                 │
│    ✓ Code validé (fenêtre de 30s)                                  │
│    ✓ TOTP enregistré pour les connexions futures                   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 8. Émission des tokens OIDC                                          │
│    Keycloak génère :                                                 │
│    - ID Token (JWT) avec claims :                                    │
│      {                                                               │
│        "sub": "alice@sase.lab",                                     │
│        "email": "alice@sase.lab",                                   │
│        "groups": ["employees", "finance"],                          │
│        "iss": "https://idp.sase.lab:8443/realms/sase",             │
│        "exp": 1732345678  # 5 minutes                               │
│      }                                                               │
│    - Access Token (opaque, 5 min)                                    │
│    Redirection vers : https://authenticate.sase.lab/oauth2/callback │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 9. Pomerium traite le callback                                       │
│    Pomerium échange l'authorization code contre les tokens           │
│    Stocke la session dans un cookie chiffré (cookie_secret)         │
│    Redirection finale vers : https://files.sase.lab                 │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 10. Évaluation de la politique ZTNA                                  │
│     Pomerium lit la config de la route "files" :                    │
│     policy:                                                          │
│       - allow:                                                       │
│           or:                                                        │
│             - claim/groups: employees                                │
│             - claim/groups: partners                                 │
│                                                                      │
│     Vérifie les claims du token :                                    │
│     alice.groups = ["employees", "finance"]                          │
│     ✓ "employees" présent → ALLOW                                   │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 11. Proxy vers mitmproxy (CASB)                                     │
│     Pomerium ajoute l'en-tête :                                      │
│     X-Pomerium-Jwt-Assertion: <JWT signé>                           │
│                                                                      │
│     Requête : GET https://files.sase.lab/                           │
│     Proxy vers : http://127.0.0.1:8081/ (mitmproxy)                │
│     └─ Boucle locale, pas de traversée réseau                       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 12. Inspection CASB/DLP (mitmproxy)                                 │
│     Add-on Python casb_dlp.py :                                      │
│     1. Extrait JWT de X-Pomerium-Jwt-Assertion                      │
│     2. Décode claims (sans vérif signature, OK car localhost)       │
│     3. Classifie l'action : "view" (consultation)                   │
│     4. Applique les règles CASB de policy.json                      │
│        Aucune règle ne bloque "view" pour employees                 │
│     5. Log événement dans /logs/casb/events.jsonl :                 │
│        {"ts": "...", "user": "alice@sase.lab",                      │
│         "groups": ["employees","finance"],                          │
│         "action": "view", "decision": "allow"}                      │
│     6. Reverse proxy vers : http://10.30.0.21:5000 (CloudDrive)    │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│ 13. Application CloudDrive                                           │
│     Flask lit X-Pomerium-Jwt-Assertion                              │
│     Affiche :                                                        │
│     "Bienvenue alice@sase.lab"                                      │
│     "Vos groupes : employees, finance"                               │
│     Liste des fichiers de alice                                      │
└──────────────────────────────────────────────────────────────────────┘
```

**Comptage des contrôles de sécurité traversés** :
1. Authentification appareil (WireGuard, clé publique)
2. Filtrage pare-feu (nftables INPUT)
3. Authentification utilisateur (Keycloak, password)
4. Second facteur (Keycloak, TOTP)
5. Autorisation par ressource (Pomerium, policy ZTNA)
6. Inspection applicative (CASB, règles par action)
7. Prévention fuite de données (DLP, si upload)

**Total : 7 couches de sécurité avant d'atteindre l'application**

---

#### Flux 2 : Accès refusé (Zero Trust)

```
Utilisateur carol (groupe : employees seulement)
Tente d'accéder à : https://finance.sase.lab

┌─────────────────────────────────────────────────────────────┐
│ 1-9. Authentification OIDC identique au Flux 1              │
│      carol se connecte avec succès, MFA validé              │
│      Session établie, cookie présent                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. Requête : GET https://finance.sase.lab/                 │
│     Client (10.100.0.12) → 10.20.0.1:443                   │
│     ✓ Tunnel WireGuard actif                               │
│     ✓ nftables INPUT : autorise                            │
│     ✓ Session Pomerium valide                              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 11. Pomerium évalue la politique de la route "finance"      │
│                                                              │
│     Configuration :                                          │
│     - from: https://finance.sase.lab                        │
│       to: http://10.30.0.22:80                             │
│       policy:                                               │
│         - allow:                                            │
│             and:                                            │
│               - claim/groups: finance                       │
│                                                              │
│     Claims de carol :                                        │
│     {                                                        │
│       "sub": "carol@sase.lab",                             │
│       "groups": ["employees"]    # ← PAS "finance"         │
│     }                                                        │
│                                                              │
│     Résultat : ✗ "finance" NOT IN carol.groups             │
│     Décision : DENY                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 12. Réponse HTTP 403 Forbidden                              │
│     Body : "Access Denied"                                   │
│     Page Pomerium : "You are not authorized to access       │
│                      this resource."                         │
│                                                              │
│     Log Pomerium :                                           │
│     {"level":"info", "user":"carol@sase.lab",               │
│      "route":"finance.sase.lab", "decision":"deny",         │
│      "reason":"policy_deny"}                                │
└─────────────────────────────────────────────────────────────┘
```

**Observation clé** : Carol est authentifiée (session valide, MFA réussi), mais l'accès est refusé par la politique spécifique à la ressource. C'est le principe **Zero Trust** : aucune confiance implicite, chaque accès est évalué.

**Différence avec l'architecture traditionnelle (VPN)** :
- Architecture VPN : Carol aurait une IP 10.0.100.x et pourrait tenter de se connecter directement au serveur Finance (192.168.10.5). Le pare-feu filtrerait seulement par IP source, sans connaître son identité ni ses droits métier.

---

#### Flux 3 : Blocage CASB (upload interdit pour partenaire)

```
Utilisateur dave (groupe : partners)
Tente de téléverser un fichier dans CloudDrive

┌─────────────────────────────────────────────────────────────┐
│ 1-11. Authentification réussie, accès files.sase.lab autorisé│
│       dave appartient au groupe "partners" (lecture seule)  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 12. Action : POST /upload avec fichier document.pdf         │
│     Client → Pomerium → mitmproxy (127.0.0.1:8081)         │
│                                                              │
│     Requête HTTP :                                           │
│     POST /upload HTTP/1.1                                    │
│     Host: files.sase.lab                                     │
│     Content-Type: multipart/form-data                        │
│     X-Pomerium-Jwt-Assertion: <JWT de dave>                 │
│     Content-Length: 45678                                    │
│     ...fichier...                                            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 13. Addon mitmproxy casb_dlp.py                             │
│                                                              │
│     1. Décode JWT :                                          │
│        dave.groups = ["partners"]                            │
│                                                              │
│     2. Classifie l'action : "upload"                        │
│        (méthode POST + path /upload)                         │
│                                                              │
│     3. Cherche règle applicable dans policy.json :          │
│        {                                                     │
│          "id": "CASB-01",                                   │
│          "description": "Partenaires : lecture seule",      │
│          "groups_any": ["partners"],                        │
│          "actions": ["upload", "delete", "share"],          │
│          "decision": "block"                                │
│        }                                                     │
│                                                              │
│     4. Évaluation :                                          │
│        ✓ dave IN groups_any (partners)                      │
│        ✓ action = "upload" IN blocked_actions               │
│        → MATCH                                              │
│                                                              │
│     5. Décision : BLOCK                                     │
│                                                              │
│     6. Log événement :                                       │
│        {"ts": "2026-11-22T14:35:42Z",                       │
│         "user": "dave@partner.lab",                         │
│         "groups": ["partners"],                             │
│         "action": "upload",                                 │
│         "filename": "document.pdf",                         │
│         "decision": "block",                                │
│         "rule": "CASB-01"}                                  │
│                                                              │
│     7. Réponse HTTP 403 :                                   │
│        Body: "Accès bloqué - Politique SASE (CASB-01)"     │
└─────────────────────────────────────────────────────────────┘
```

**Observation clé** : Dave peut consulter et télécharger des fichiers (actions autorisées pour partners), mais pas les téléverser, supprimer ou partager. Le contrôle est **granulaire au niveau de l'action applicative**, pas seulement de la ressource.

---

#### Flux 4 : Détection DLP (carte bancaire)

```
Utilisateur alice (groupe : employees, finance)
Téléverse un fichier contenant un numéro de carte bancaire

┌─────────────────────────────────────────────────────────────┐
│ 1-12. Authentification + ZTNA + CASB action "upload"        │
│       ✓ alice autorisée à téléverser                        │
│       ✓ Règle CASB-03 : vérifier extension fichier          │
│       ✓ Fichier : carte_bancaire.txt (pas .exe) → continue │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 13. Inspection DLP (dlp_engine.py)                          │
│                                                              │
│     Contenu du fichier carte_bancaire.txt :                 │
│     """                                                      │
│     Numéro de carte : 4111 1111 1111 1111                   │
│     Date d'expiration : 12/25                               │
│     CVV : 123                                               │
│     """                                                      │
│                                                              │
│     Moteur DLP cherche motifs sensibles :                   │
│                                                              │
│     1. Regex carte bancaire :                               │
│        \b[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b│
│        Candidat trouvé : "4111111111111111"                 │
│                                                              │
│     2. Validation algorithme de Luhn :                      │
│        Somme = (4×2) + 1 + (1×2) + 1 + (1×2) + 1 + ...     │
│              + (1×2) + 1 + (1×2) + 1 + 1                    │
│              = 8+1+2+1+2+1+2+1+2+1+2+1+2+1+2+1+2+1+1 = 40  │
│        40 % 10 = 0 ✓ Valide                                │
│                                                              │
│     3. Règle DLP trouvée :                                  │
│        "CARTE_BANCAIRE" IN policy.dlp.block                 │
│                                                              │
│     4. Décision : BLOCK                                     │
│                                                              │
│     5. Log événement (sans recopier les données) :         │
│        {"ts": "...", "user": "alice@sase.lab",             │
│         "action": "upload", "filename": "carte_bancaire.txt",│
│         "decision": "block",                                │
│         "rule": "DLP-CARTE_BANCAIRE",                       │
│         "dlp_hits": {"CARTE_BANCAIRE": 1}}                 │
│                                                              │
│     6. Réponse HTTP 403 :                                   │
│        "Accès bloqué - Politique SASE (DLP-CARTE_BANCAIRE)"│
└─────────────────────────────────────────────────────────────┘
```

**Justification technique de l'algorithme de Luhn** :
- Sans validation, la regex `\b[0-9]{16}\b` générerait des **faux positifs** sur n'importe quelle suite de 16 chiffres (numéro de série, identifiant, etc.)
- L'algorithme de Luhn vérifie la cohérence mathématique : seuls les vrais numéros de carte (ou générés avec Luhn) passent
- Taux de faux positifs estimé : <1% (vs ~90% avec regex simple)

**Autres validations implémentées** :
- **IBAN français** : modulo 97 (ISO 7064)
- **NIR (Sécurité Sociale)** : clé de contrôle à 2 chiffres
- **Signature EICAR** : chaîne exacte de test antivirus
- **Clé AWS** : regex précise `AKIA[0-9A-Z]{16}`

**Limitation connue** : Fichiers binaires (PDF, DOCX, images) non analysés. DLP niveau N2.

---

#### Flux 5 : Navigation web via SWG

```
Utilisateur depuis branch-pc (succursale)
Navigateur configuré avec proxy : http://10.20.0.1:3128

┌─────────────────────────────────────────────────────────────┐
│ 1. Requête : http://news.inet.lab/article.html              │
│    Navigateur → Proxy Squid (10.20.0.1:3128)               │
│    Via tunnels wg-b1 ou wg-b2 (selon classe SD-WAN)        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Squid évalue ACL                                          │
│                                                              │
│    acl users src 10.100.0.0/24 192.168.10.0/24             │
│    Source : 192.168.10.10 (branch-pc) ✓ Match              │
│                                                              │
│    acl Safe_ports port 80 443                               │
│    Port : 80 ✓ Match                                        │
│                                                              │
│    acl blocked_domains dstdomain "/etc/squid/blocked_domains.txt"│
│    Domaine : news.inet.lab                                   │
│    Fichier ne contient pas news.inet.lab ✓ Pas match       │
│                                                              │
│    acl blocked_urls url_regex -i "/etc/squid/blocked_urls.txt"│
│    URL complète : http://news.inet.lab/article.html         │
│    Fichier contient : /gambling/ /adult/                    │
│    ✓ Pas match                                              │
│                                                              │
│    acl blocked_ext urlpath_regex -i \.(exe|msi|scr|bat)$   │
│    Path : /article.html                                      │
│    ✓ Pas match                                              │
│                                                              │
│    Décision finale : http_access allow users → ALLOW        │
│                                                              │
│    Log : 1732345678.123 TCP_MISS/200 GET                    │
│          http://news.inet.lab/article.html                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Squid forward vers inet-sim (10.20.0.70:80)             │
│    Réponse 200 OK avec contenu HTML                         │
│    Transfert au client via wg-b1                            │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────

Contre-exemple : Site bloqué

┌─────────────────────────────────────────────────────────────┐
│ 1. Requête : http://casino.inet.lab/                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Squid évalue ACL                                          │
│    acl blocked_domains dstdomain ...                        │
│    casino.inet.lab IN blocked_domains.txt ✓ Match          │
│                                                              │
│    http_access deny blocked_domains → DENY                 │
│                                                              │
│    Log : 1732345680.456 TCP_DENIED/403 GET                 │
│          http://casino.inet.lab/                            │
│                                                              │
│    Réponse : HTTP/1.1 403 Forbidden                        │
│    Body : ERR_ACCESS_DENIED (page Squid)                   │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────

Requête HTTPS

┌─────────────────────────────────────────────────────────────┐
│ 1. Requête : https://www.facebook.com/                      │
│    Navigateur → Proxy Squid                                 │
│    Méthode : CONNECT (établissement tunnel TLS)             │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Squid évalue CONNECT                                     │
│                                                              │
│    acl SSL_ports port 443                                   │
│    Port : 443 ✓ Match                                       │
│                                                              │
│    acl CONNECT method CONNECT                               │
│    ✓ Match                                                  │
│                                                              │
│    acl blocked_domains dstdomain ...                        │
│    www.facebook.com IN blocked_domains.txt ✓ Match         │
│                                                              │
│    http_access deny blocked_domains → DENY                 │
│                                                              │
│    Réponse : HTTP/1.1 403 Forbidden                        │
│    Body : ERR_CONNECT_FAIL (tunnel refusé)                 │
│                                                              │
│    Note : Sans ssl_bump, Squid ne voit que le domaine      │
│           dans CONNECT, pas l'URL complète ni le contenu   │
└─────────────────────────────────────────────────────────────┘
```

**Niveau de réalisation** :
- HTTP (clair) : N1 (domaine, URL, extension, contenu)
- HTTPS : N2 (domaine seulement via CONNECT, pas de contenu)

---

#### Flux 6 : Bascule SD-WAN automatique

```
État initial : wg-b1 optimal (RTT 5ms, perte 0%)
               wg-b2 optimal (RTT 6ms, perte 0%)

branch-edge route tables :
  Table 101 (business) : default via 172.16.1.1 dev wg-b1
  Table 102 (realtime) : default via 172.16.1.1 dev wg-b1 (meilleur score)
  Main (bulk)          : default via 172.16.2.1 dev wg-b2

┌─────────────────────────────────────────────────────────────┐
│ T=0s : Dégradation du lien wan1 (porte wg-b1)              │
│        $ docker exec branch-edge impair wan1 set            │
│            delay 250ms loss 30%                             │
│                                                              │
│        (simule congestion réseau ou panne partielle)        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ T=0s-2s : Agent SD-WAN continue ses mesures toutes les 2s  │
│                                                              │
│           Mesure wg-b1 :                                    │
│           ping -c 3 -W 1 10.20.0.1  via  10.10.1.1         │
│           RTT moyen : 255ms (+ netem 250ms)                │
│           Perte : 30%                                       │
│                                                              │
│           Mesure wg-b2 :                                    │
│           ping -c 3 -W 1 10.20.0.1  via  10.10.2.1         │
│           RTT moyen : 6ms                                   │
│           Perte : 0%                                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ T=2s : Évaluation de l'agent                                │
│                                                              │
│        Politique (sdwan-policy.env) :                       │
│        RTT_MAX=120ms, LOSS_MAX=20%                          │
│                                                              │
│        Lien wg-b1 :                                         │
│        ✗ RTT 255ms > 120ms  → DÉGRADÉ                      │
│        ✗ Perte 30% > 20%    → DÉGRADÉ                      │
│                                                              │
│        Lien wg-b2 :                                         │
│        ✓ RTT 6ms < 120ms                                   │
│        ✓ Perte 0% < 20%     → OPTIMAL                      │
│                                                              │
│        Calcul scores :                                       │
│        Score(wg-b1) = RTT + 20×perte = 255 + 20×30 = 855   │
│        Score(wg-b2) = RTT + 20×perte = 6 + 20×0 = 6        │
│                                                              │
│        Meilleur lien : wg-b2                                │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ T=2s : Décision de bascule                                  │
│                                                              │
│        Classe BUSINESS (préférence wg-b1) :                │
│        Lien préféré wg-b1 DÉGRADÉ                          │
│        → Bascule sur wg-b2                                 │
│        $ ip route replace default via 172.16.2.1 dev wg-b2 table 101│
│                                                              │
│        Classe REALTIME (meilleur score) :                  │
│        Meilleur lien = wg-b2 (déjà actif)                  │
│        → Pas de changement table 102                       │
│                                                              │
│        Classe BULK (préférence wg-b2) :                    │
│        Lien préféré wg-b2 OPTIMAL                          │
│        → Pas de changement main table                      │
│                                                              │
│        Log agent :                                           │
│        {"ts":"...","link":"wg-b1","rtt":255,"loss":30,      │
│         "status":"degraded"}                                │
│        {"ts":"...","link":"wg-b2","rtt":6,"loss":0,         │
│         "status":"optimal"}                                 │
│        {"ts":"...","class":"business","path":"wg-b2",       │
│         "reason":"primary_degraded"}                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ T=2s-10s : Trafic business bascule instantanément           │
│                                                              │
│            Nouveau paquet TCP/443 de branch-pc :            │
│            1. nftables mark set 0x1 (business)             │
│            2. ip rule : fwmark 0x1 lookup 101              │
│            3. Table 101 : default via wg-b2                │
│            4. Paquet routé via wg-b2 (pas de coupure TCP)  │
│                                                              │
│            Les connexions TCP établies via wg-b1 continuent│
│            jusqu'à leur fin naturelle ou timeout           │
│            Nouvelles connexions passent par wg-b2          │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ T=60s : Rétablissement du lien wan1                         │
│         $ docker exec branch-edge impair wan1 clear         │
│                                                              │
│         (netem désactivé, lien revient à la normale)        │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│ T=62s : Agent détecte le rétablissement                     │
│                                                              │
│         Mesure wg-b1 :                                      │
│         RTT moyen : 5ms, Perte : 0% → OPTIMAL              │
│                                                              │
│         Score(wg-b1) = 5 + 20×0 = 5                        │
│         Score(wg-b2) = 6 + 20×0 = 6                        │
│                                                              │
│         Classe BUSINESS :                                   │
│         Lien préféré wg-b1 OPTIMAL                         │
│         → Retour sur wg-b1                                 │
│         $ ip route replace default via 172.16.1.1 dev wg-b1 table 101│
│                                                              │
│         Log : {"class":"business","path":"wg-b1",           │
│                "reason":"primary_restored"}                 │
└─────────────────────────────────────────────────────────────┘
```

**Temps de bascule mesuré** : 2-4 secondes (dépend de INTERVAL=2s et du moment où la dégradation survient dans le cycle de mesure)

**Absence d'hystérésis** : L'agent bascule immédiatement dès que le seuil est franchi. Conséquence : en cas de qualité fluctuant autour du seuil, des oscillations (flapping) peuvent se produire. Solution (hors périmètre) : ajouter un compteur de cycles dégradés consécutifs avant bascule.

**Niveau de réalisation** : N2 (SD-WAN réel avec mesure SLA et bascule automatique, mais contrôleur simplifié et pas d'hystérésis)

---

### 4.4.4 Synthèse des flux de sécurité

Le tableau 4.05 résume les flux documentés et les contrôles de sécurité traversés.

**Tableau 4.05 : Synthèse des flux et contrôles de sécurité**

| Flux | Origine | Destination | Contrôles traversés | Résultat attendu |
|------|---------|-------------|---------------------|------------------|
| **Flux 1 : Authentification OIDC** | home-laptop (10.100.0.11) | CloudDrive (10.30.0.21) | WireGuard, nftables INPUT, Keycloak (password+MFA), Pomerium (policy), mitmproxy (CASB) | Page CloudDrive avec identité affichée |
| **Flux 2 : Accès refusé ZTNA** | carol (10.100.0.12) | Finance (10.30.0.22) | WireGuard, nftables, Keycloak, Pomerium policy | HTTP 403, log "policy_deny" |
| **Flux 3 : Blocage CASB** | dave (partners) | CloudDrive upload | Tous précédents + CASB rule match | HTTP 403, log "CASB-01" |
| **Flux 4 : Détection DLP** | alice | CloudDrive upload CB | Tous précédents + DLP Luhn validation | HTTP 403, log "DLP-CARTE_BANCAIRE" |
| **Flux 5 : SWG autorise** | branch-pc | news.inet.lab | wg-b2, nftables, Squid ACL | HTTP 200, log TCP_MISS |
| **Flux 5b : SWG bloque** | branch-pc | casino.inet.lab | wg-b2, nftables, Squid blocked_domains | HTTP 403, log TCP_DENIED |
| **Flux 6 : SD-WAN bascule** | branch-pc (TCP/443) | PoP services | Agent SLA détecte wg-b1 dégradé, modifie table 101 | Trafic business via wg-b2, log "primary_degraded" |

**Total de composants de sécurité implémentés et testés** : 9
1. Authentification appareil (WireGuard)
2. Pare-feu centralisé (nftables FWaaS)
3. IAM avec MFA (Keycloak OIDC + TOTP)
4. ZTNA par ressource (Pomerium)
5. Filtrage DNS (dnsmasq sinkhole)
6. SWG proxy web (Squid)
7. CASB contrôle d'actions (mitmproxy)
8. DLP prévention fuite (dlp_engine.py)
9. SD-WAN multi-chemins (WireGuard + agent SLA)

---

**Ce chapitre est incomplet. La suite à venir dans le prochain message inclura :**

- **4.5 Implémentation détaillée des composants clés** (WireGuard, nftables, Keycloak, Pomerium, CASB, DLP, SD-WAN)
- **4.6 Configurations techniques avec extraits de code réels**
- **4.7 Déploiement et intégration pas à pas**
- **4.8 Validation fonctionnelle et scénarios de test**
- **4.9 Métriques de performance et analyse des résultats**
- **4.10 Bilan technique, limites et perspectives**

**Voulez-vous que je continue avec ces sections ?**
