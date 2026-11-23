# CHAPITRE 4 — RÉALISATION, DÉPLOIEMENT ET RÉSULTATS EXPÉRIMENTAUX

## 4.1 Introduction

Les chapitres précédents ont établi le cadre théorique du travail : l'état de l'art des accès distants aux ressources cloud, l'architecture SASE et ses composants, puis le modèle mathématique qui décrit son comportement. Ce chapitre rend compte de la réalisation. Il explique comment j'ai remplacé une architecture d'accès distant classique, fondée sur un VPN et un pare-feu périmétrique, par un point de présence SASE déployé sur un ordinateur portable de 8 Go de mémoire vive, puis comment j'ai éprouvé le résultat.

Le chapitre suit l'ordre réel du travail. Je présente d'abord la démarche et l'environnement expérimental (4.2), puis la situation de départ (4.3) et l'architecture cible (4.4), de façon à montrer précisément ce que le passage à SASE change. La mise en œuvre est ensuite détaillée étape par étape, avec les extraits de configuration qui portent les décisions techniques (4.5). Le cheminement d'une connexion dans l'architecture obtenue (4.6), les scénarios de validation (4.7) et les mesures de ressources, de latence et de reprise (4.8) confrontent la réalisation aux propriétés attendues et aux hypothèses du chapitre 3. Un bilan (4.9) clôt le chapitre.

Trois statuts d'information sont distingués tout au long du texte : ce qui est **configuré** (un paramètre de conception, un fichier, une règle), ce qui est **observé** (une sortie de commande, un journal, une capture) et ce qui reste **attendu ou à mesurer** (une hypothèse non encore vérifiée). Cette distinction commande le niveau de réalisation attribué à chaque fonction : **N1** lorsque la fonction est implémentée et testée avec preuve, **N2** lorsqu'elle est réelle mais de profondeur réduite ou complétée par un script de démonstration, **N3** lorsqu'elle est théorique ou hors de portée de la maquette. Aucune fonction n'est présentée comme opérationnelle sans test réussi.

## 4.2 Démarche de réalisation et environnement expérimental

### 4.2.1 Objectifs et périmètre

L'objectif général est de concevoir, déployer et valider un laboratoire SASE cohérent, démontrable devant un jury, qui sécurise l'accès d'utilisateurs distants à des applications cloud d'entreprise. Il se décline en six objectifs spécifiques :

- authentifier les utilisateurs de façon centralisée (OIDC, groupes, MFA par TOTP) et ne jamais faire confiance au réseau ;
- n'ouvrir l'accès qu'aux applications autorisées, par identité, depuis trois contextes : le domicile, le déplacement et le bureau ;
- inspecter et filtrer le trafic : pare-feu centralisé (FWaaS), passerelle web sécurisée (SWG) et filtrage DNS ;
- contrôler l'usage d'une application SaaS de test (CASB) et prévenir la fuite de données fictives (DLP) ;
- illustrer un routage multi-chemins avec bascule automatique sur dégradation d'un lien (SD-WAN) ;
- centraliser la supervision et documenter honnêtement le niveau de réalisation de chaque fonction.

Le périmètre comprend un PoP unique, trois contextes d'accès, trois applications (CloudDrive, qui joue le rôle de SaaS de test, Finance et Admin), un environnement qui simule Internet, deux liens WAN simulés et cinq comptes de test. Restent hors périmètre : un réseau mondial de PoP, l'élasticité cloud, l'inspection TLS généralisée, un agent ZTNA de couche 3 avec posture complète de l'appareil, un CASB en mode API, un DLP par empreinte ou par OCR, un IPS ou un antivirus réseau et un contrôleur SD-WAN commercial. Les conclusions sont donc limitées aux fonctions réellement représentées.

### 4.2.2 Méthode : onze étapes avec point de contrôle

J'ai conduit la réalisation en onze étapes, numérotées de 0 à 10 (figure 4.01). Chaque étape suit le même enchaînement : préparation, installation, configuration, puis vérification. Le passage à l'étape suivante est conditionné par une vérification concluante, de façon à localiser une panne dans l'étape qui la provoque plutôt que dans l'ensemble de la chaîne. Cette discipline est particulièrement utile dans une architecture où cinq services partagent la même pile réseau : une erreur d'adressage ou de certificat se manifeste très loin de sa cause.

![Figure 4.01 — Démarche de réalisation en onze étapes, chacune assortie d'une vérification.](topo/png/doc/fig4_01_etapes.png){width=16cm}

### 4.2.3 Plateforme matérielle et contrainte des 8 Go

La plateforme expérimentale est un ordinateur portable Dell Latitude 3500 : processeur Intel Core i5-8265U (huit processeurs logiques), Windows 10 Professionnel 64 bits, 8 Go de mémoire vive et un SSD de 120 Go. Un système Windows inactif consomme typiquement 3 à 4 Go, valeur contrôlée dans le Gestionnaire des tâches. Il reste donc environ 4 Go pour l'hyperviseur, la maquette et le navigateur.

Une approche « une machine virtuelle par fonction » — un pare-feu pfSense ou OPNsense de 1 à 2 Go, un contrôleur SD-WAN, un serveur d'identité et un SIEM — est de ce fait exclue. Trois décisions structurent la solution retenue :

- **une seule VM Linux de 3 Go** sous VirtualBox, qui héberge tous les services sous forme de conteneurs Docker. J'ai écarté Docker Desktop avec WSL2, dont la consommation mémoire n'est pas plafonnée et dont le comportement réseau en UDP est moins prévisible ;
- **l'hôte Windows joue le rôle de poste distant** : il porte le client WireGuard et le navigateur, de sorte qu'aucun client supplémentaire n'est chargé en mémoire. La succursale est simulée par deux conteneurs de quelques mégaoctets ;
- **des briques légères et spécialisées** (nftables, WireGuard, Squid, dnsmasq, Pomerium, mitmproxy, Loki) à la place de suites monolithiques (Wazuh, ELK, ClamAV, Authentik) qui dépasseraient à elles seules le budget mémoire.

Ce choix a un coût que je garde à l'esprit pour l'interprétation des résultats : la concentration des fonctions dans une VM crée un domaine de panne commun. L'indisponibilité de la VM, ou du conteneur de passerelle qui porte la pile réseau, interrompt simultanément plusieurs fonctions du PoP.

### 4.2.4 Choix technologiques et paramètres de la machine virtuelle

Chaque outil a été retenu pour son adéquation fonctionnelle, son empreinte mémoire et sa capacité à s'intégrer dans une chaîne cohérente. Le tableau 4.01 récapitule les choix ; les consommations indiquées sont des estimations de dimensionnement, confrontées aux mesures réelles à la section 4.8.1.

| Outil | Composante SASE | Licence | RAM estimée | Raison du choix |
|:--|:--|:--|:--|:--|
| WireGuard | Entrée du PoP, tunnels SD-WAN | GPLv2 | intégré au noyau | Authentification de l'appareil par clé publique, coût mémoire nul |
| nftables | FWaaS | GPLv2 | intégré au noyau | Pare-feu à états natif, politique versionnée dans un fichier |
| Keycloak | IAM, MFA TOTP | Apache-2.0 | 600 à 800 Mo | OIDC, groupes, journal d'événements ; tas plafonné à 640 Mo |
| Pomerium | ZTNA sans agent | Apache-2.0 | 100 à 200 Mo | Politique par route et par groupe, OIDC natif |
| Squid | SWG | GPLv2 | 40 à 80 Mo | ACL sur domaine, URL et extension, sans cache disque |
| dnsmasq | Filtrage DNS | GPLv2/v3 | moins de 10 Mo | Puits DNS et journal des requêtes |
| mitmproxy | CASB et DLP | MIT | 100 à 150 Mo | Add-on Python en reverse proxy, accès au corps des requêtes |
| Fluent Bit, Loki, Grafana | Supervision | Apache-2.0, AGPLv3 | environ 300 Mo | Index minimal par étiquettes, sans ELK |
| VirtualBox, Ubuntu, Docker | Socle | libres | environ 500 Mo | Images reproductibles, mémoire plafonnée |

: Tableau 4.01 — Synthèse des outils retenus et de leur empreinte estimée

Les alternatives ont été écartées surtout pour leur coût opérationnel ou leur empreinte : flexiWAN demande un contrôleur et plusieurs gigaoctets, pfSense et OPNsense exigent une VM de 1 à 2 Go, Authentik (environ 1,5 Go avec sa base) et Wazuh ou ELK (2 à 4 Go) dépasseraient le budget, et ClamAV occupe à lui seul plus de 1 Go. Ce choix ne signifie pas que ces solutions sont moins performantes dans l'absolu ; il traduit un compromis entre couverture fonctionnelle et faisabilité locale.

| Paramètre VirtualBox | Valeur retenue |
|:--|:--|
| Nom et type | sase-pop ; Linux, Ubuntu (64 bits) |
| Mémoire et processeurs | 3 072 Mo ; 2 vCPU |
| Disque | VDI à allocation dynamique, 25 Go |
| Carte 1 | NAT (enp0s3, 10.0.2.15/24) : accès Internet de la VM |
| Carte 2 | Host-only (enp0s8, 192.168.56.10/24) : point d'entrée du PoP |
| Installation | Ubuntu Server 24.04, profil minimal, utilisateur `sase`, serveur OpenSSH |

: Tableau 4.02 — Paramètres de la machine virtuelle sase-pop

Trois composants structurent le contrôle d'accès et jouent des rôles volontairement distincts. WireGuard constitue la frontière de l'overlay : un paquet issu d'un pair inconnu n'est pas traité comme celui d'un pair enregistré. Keycloak est le fournisseur d'identité et émet les assertions OIDC. Pomerium consomme ces assertions et décide de l'autorisation pour chaque route publiée. La possession d'une clé WireGuard ne prouve donc pas l'identité de la personne, et une authentification réussie ne donne pas accès à toutes les applications.

## 4.3 Situation de départ : la topologie AVANT SASE

### 4.3.1 Architecture de référence

Pour mesurer l'apport de SASE, il faut d'abord décrire ce qu'il remplace. La figure 4.02 représente l'architecture d'accès distant la plus répandue dans les entreprises, celle dont le chapitre 1 a montré les limites. Je l'ai reconstituée pour qu'elle porte exactement les mêmes acteurs que la maquette : un utilisateur à domicile, un utilisateur en déplacement, une succursale, trois applications privées, une application SaaS et l'accès au web.

![Figure 4.02 — Topologie de référence avant SASE : VPN d'accès distant et pare-feu périmétrique.](topo/png/doc/fig4_02_avant.png){width=16cm}

Dans cette topologie, tout converge vers le siège. Les utilisateurs distants établissent un tunnel VPN (IPsec ou SSL) vers un concentrateur placé derrière le pare-feu périmétrique ; une fois authentifiés auprès de l'annuaire, ils reçoivent une adresse du réseau interne et rejoignent le même réseau à plat que les postes du siège. Les applications privées y sont joignables par leur adresse IP. La succursale est reliée au siège par un lien unique (MPLS ou VPN site-à-site). Le trafic web et SaaS des télétravailleurs est soit envoyé directement sur Internet, sans contrôle, soit ramené par le tunnel jusqu'au proxy du siège avant de ressortir : c'est le **backhaul**. Les journaux du pare-feu, du concentrateur VPN et du proxy sont produits et conservés séparément.

Cette topologie de référence n'a pas été déployée dans la maquette : je l'utilise comme point de comparaison. La confrontation entre l'avant et l'après porte donc sur les propriétés des deux architectures et sur les observations faites sur la maquette SASE, et non sur des mesures comparées des deux chaînes.

### 4.3.2 Limites constatées de l'architecture de référence

Les six repères de la figure 4.02 correspondent aux limites analysées dans le tableau 4.03. Chaque ligne indique la fonction SASE qui y répond dans l'architecture réalisée.

| Repère | Limite constatée | Conséquence | Réponse dans la maquette SASE |
|:--|:--|:--|:--|
| L1 | Confiance implicite : le VPN donne un accès réseau étendu après une authentification unique | Un compte ou un poste compromis atteint tout le réseau interne (déplacement latéral) | Tunnel limité au PoP ; autorisation par application et par groupe ; pare-feu en refus par défaut |
| L2 | Retour du trafic SaaS et web par le siège, ou sortie directe non filtrée | Latence accrue, lien du siège saturé, aucune politique web | SWG et DNS filtrant dans le PoP ; chemin web distinct du chemin applicatif |
| L3 | Politiques réparties sur trois équipements, exprimées par adresses IP | Règles incohérentes, difficiles à auditer, sans notion d'utilisateur | Identité commune (OIDC) et politiques sous forme de fichiers versionnés |
| L4 | Journaux séparés par équipement | Reconstitution d'un incident lente et incertaine | Chaîne unique Fluent Bit, Loki, Grafana ; composants étiquetés |
| L5 | Lien unique, sans mesure de qualité | Aucune bascule en cas de dégradation | Deux tunnels, mesure du SLA, routage par politique |
| L6 | Aucun contrôle des actions ni des contenus dans les applications cloud | Partage public ou fuite de données non détectés | CASB et DLP en ligne devant l'application SaaS de test |

: Tableau 4.03 — Limites de l'architecture avant SASE et réponse apportée par la maquette

## 4.4 Architecture cible : la topologie APRÈS SASE

### 4.4.1 Vue logique et fonctions traversées

La figure 4.03 présente l'architecture que j'ai réalisée, dessinée selon la même convention que la figure 4.02 afin que les deux se lisent en parallèle. Trois changements structurent le passage de l'une à l'autre. Premièrement, le tunnel change de nature : sur le poste distant, les routes autorisées par WireGuard se limitent au sous-réseau des services du PoP (10.20.0.0/24) et à l'adresse de la passerelle de l'overlay (10.100.0.1/32). Le réseau des applications (10.30.0.0/24) n'apparaît dans aucune route cliente. Deuxièmement, les fonctions de sécurité sont réunies dans un seul nœud, dans l'ordre où une requête les traverse. Troisièmement, tous les composants alimentent une même supervision.

![Figure 4.03 — Topologie après SASE : un PoP unique et les fonctions traversées par une requête.](topo/png/doc/fig4_03_apres.png){width=16cm}

Les six blocs de la figure se lisent ainsi :

- **A, entrée sécurisée** : WireGuard authentifie l'appareil par sa clé publique (interfaces `wg0` pour les utilisateurs, `wg-b1` et `wg-b2` pour la succursale) ;
- **B, FWaaS** : nftables applique une politique de refus par défaut sur les trois chaînes INPUT, FORWARD et OUTPUT et journalise les refus ;
- **C, DNS filtrant et SWG** : dnsmasq neutralise les noms interdits avant la connexion, Squid filtre les requêtes web par domaine, URL et extension ;
- **D, ZTNA et IAM** : Keycloak authentifie l'utilisateur (mot de passe et TOTP) et Pomerium décide de l'accès à chaque application selon les groupes ;
- **E, CASB et DLP** : mitmproxy, placé en reverse proxy devant CloudDrive, contrôle chaque action et analyse le contenu des fichiers téléversés ;
- **F, supervision** : Fluent Bit, Loki et Grafana rassemblent les journaux de tous les blocs.

Deux flux sortent du PoP et se distinguent par la couleur : en vert, le flux web, de la passerelle SWG vers Internet ; en rouge, le flux applicatif, du CASB vers le réseau des applications, porteur du jeton d'identité de l'utilisateur. Les deux traversent le même nœud, mais ne rencontrent pas les mêmes contrôles : le premier ne voit qu'un nom d'hôte et une URL, le second dispose de l'identité, du groupe et du contenu.

### 4.4.2 Topologie physique et virtuelle

La figure 4.04 donne le détail de la maquette. L'hôte Windows (192.168.56.1) porte le client WireGuard et un profil de navigateur dédié. Il est relié à la VM « sase-pop » par une interface host-only (192.168.56.10), qui constitue l'adresse « publique » du PoP et le seul point d'entrée : un unique port est publié, UDP 51820. Une seconde interface en NAT (10.0.2.15) sert uniquement aux téléchargements. À l'intérieur de la VM, cinq réseaux Docker séparent les services du PoP (`svc`), les applications privées (`apps`), les deux supports de transport simulés (`wan1`, `wan2`) et le LAN de la succursale (`branch_lan`). Les quatre derniers sont déclarés internes : ils n'ont aucune sortie vers Internet.

![Figure 4.04 — Topologie physique et virtuelle de la maquette : hôte Windows, VM sase-pop et réseaux Docker.](topo/png/doc/fig4_04_virtuelle.png){width=16cm}

Le choix structurant est la **pile réseau partagée**. Le conteneur `pop-gw` possède les interfaces du PoP (WireGuard, adresses sur `svc`, `apps`, `wan1` et `wan2`) et le pare-feu nftables ; Keycloak, Pomerium, Squid, dnsmasq et mitmproxy s'exécutent dans d'autres conteneurs qui rejoignent sa pile réseau (`network_mode: service:pop-gw`). Ils partagent donc l'adresse 10.20.0.1. Ce montage a deux avantages : le pare-feu voit l'ensemble du trafic entrant, et les adresses sources réelles des clients restent visibles dans chaque journal. Il a un inconvénient assumé : `pop-gw` devient un point de défaillance critique.

### 4.4.3 Plan d'adressage

Les tableaux 4.04 et 4.05 fixent le plan d'adressage et les flux autorisés. Les adresses, domaines et ports sont identiques dans tout le chapitre. La zone DNS `sase.lab`, résolue en 10.20.0.1, regroupe les services publiés (`authenticate`, `idp`, `files`, `finance`, `admin`, `grafana`) ; la zone `inet.lab`, résolue en 10.20.0.70, simule Internet avec des destinations autorisées et interdites (`news`, `casino`, `malware`, `phishing`).

| Réseau | Sous-réseau | Équipements | Rôle |
|:--|:--|:--|:--|
| Host-only VirtualBox | 192.168.56.0/24 | Hôte .1 ; VM .10 | Adresse « publique » du PoP |
| NAT VirtualBox | 10.0.2.0/24 | VM 10.0.2.15 | Accès Internet de la VM |
| `wg0` | 10.100.0.0/24 | PoP .1 ; home-laptop .11 ; mobile .12 | Overlay des utilisateurs |
| `wg-b1`, `wg-b2` | 172.16.1.0/30, 172.16.2.0/30 | PoP .1 ; edge .2 | Tunnels SD-WAN |
| `svc` | 10.20.0.0/24 | pop-gw .1 ; Grafana .60 ; Loki .61 ; Fluent Bit .62 ; inet-sim .70 | Services du PoP |
| `apps` (interne) | 10.30.0.0/24 | pop-gw .1 ; CloudDrive .21 ; Finance .22 ; Admin .23 | Applications privées |
| `wan1`, `wan2` (internes) | 10.10.1.0/24, 10.10.2.0/24 | pop-gw .1 ; branch-edge .2 | Sous-couche SD-WAN |
| `branch_lan` (interne) | 192.168.10.0/24 | branch-edge .1 ; branch-pc .10 | LAN de la succursale |

: Tableau 4.04 — Plan d'adressage de la maquette

| Flux | Protocole et port | Source vers destination | Contrôle appliqué |
|:--|:--|:--|:--|
| Tunnel utilisateur | UDP 51820 | Poste Windows vers 192.168.56.10 | Clé publique enregistrée ; règle INPUT |
| Tunnels succursale | UDP 51821 et 51822 | branch-edge vers 10.10.1.1 et 10.10.2.1 | Règle INPUT par adresse source |
| Résolution DNS | UDP/TCP 53 | Clients du tunnel vers 10.100.0.1 ou 10.20.0.1 | INPUT depuis les tunnels ; puits DNS |
| Accès aux applications | TCP 443 | Clients vers Pomerium | ZTNA par identité |
| Authentification | TCP 8443 | Navigateur et Pomerium vers Keycloak | MFA par TOTP |
| Navigation web | TCP 3128 | Clients vers Squid, puis Internet 80/443 | ACL du SWG ; filtrage sortant |
| Contrôle SaaS | HTTP 8081 (boucle locale) | Pomerium vers mitmproxy vers 10.30.0.21:5000 | CASB et DLP |
| Applications privées | HTTP 80 | Pomerium vers 10.30.0.22 et 10.30.0.23 | Aucun accès direct (FORWARD en refus) |
| Journalisation | TCP 24224 et 3100 | Docker vers Fluent Bit vers Loki | Réseau `svc` |
| Tests SD-WAN | TCP/UDP 5201 | branch-pc vers pop-gw | INPUT depuis les tunnels |

: Tableau 4.05 — Flux, protocoles et contrôles associés

### 4.4.4 Ce que change le passage à SASE

Le tableau 4.06 met en regard les deux architectures sur neuf dimensions. Il résume la thèse du chapitre : un VPN suivi d'un pare-feu accorde un accès réseau puis filtre des ports, alors que l'architecture réalisée n'ouvre que le PoP, décide ensuite de l'accès à chaque application selon l'identité, contrôle les actions et les contenus, filtre le web dans le même nœud et conserve la trace de chaque décision. C'est cette convergence pilotée par l'identité, et non l'empilement de fonctions, qui caractérise SASE.

| Dimension | Avant SASE (VPN et pare-feu) | Avec SASE (maquette) |
|:--|:--|:--|
| Accès distant | Tunnel VPN donnant un accès IP au réseau interne | Tunnel WireGuard limité au PoP (10.20.0.0/24 et 10.100.0.1/32) |
| Authentification | Compte d'annuaire vérifié par le concentrateur VPN | OIDC Keycloak avec TOTP ; jeton portant l'identité et les groupes |
| Autorisation | Règles par adresse IP ou VLAN | Politique par route et par groupe (Pomerium), puis par action (CASB) |
| Applications privées | Réseau à plat joignable depuis le VPN | Réseau `apps` interne, sans Internet, FORWARD en refus par défaut |
| Trafic web | Direct, ou ramené par le siège (backhaul) | SWG et DNS filtrant du PoP, chemin distinct des applications |
| SaaS et données | Aucun contrôle des actions ni des contenus | CASB et DLP en ligne : règles par groupe, détection validée par algorithmes |
| Succursale | Lien unique, sans mesure de qualité | Deux tunnels, trois classes de trafic, bascule selon le SLA mesuré |
| Journalisation | Un journal par équipement | Chaîne unique Fluent Bit, Loki, Grafana ; sept sources étiquetées |
| Gestion de la politique | Console propre à chaque équipement | Fichiers versionnés et identité commune (Keycloak) |

: Tableau 4.06 — Comparaison de l'architecture de référence et de l'architecture SASE réalisée

## 4.5 Mise en œuvre pas à pas et extraits de configuration

Cette section relate la réalisation dans l'ordre où je l'ai menée. Pour chaque étape, j'indique ce que j'ai fait, la raison technique de ce choix et la vérification qui m'a permis de la considérer comme acquise. Seuls les extraits utiles à la compréhension sont reproduits ; l'ensemble des fichiers constitue le dépôt `sase-lab`, dont l'arborescence figure en annexe 4.A.

### 4.5.1 Étapes 0 et 1 : l'hôte Windows et la machine virtuelle

J'ai commencé par l'hôte. J'ai vérifié dans le Gestionnaire des tâches que la virtualisation matérielle (Intel VT-x) était activée, libéré environ 40 Go de disque, puis installé VirtualBox 7.x, l'image ISO d'Ubuntu Server 24.04 LTS, le client WireGuard pour Windows et le navigateur Microsoft Edge. Hyper-V ralentit VirtualBox lorsqu'il reste actif sur l'hôte ; il est donc désactivé pour les mesures.

J'ai ensuite créé, depuis le Gestionnaire de réseau de VirtualBox, un réseau host-only 192.168.56.0/24 dont le serveur DHCP est désactivé. Ce réseau joue le rôle de réseau « public » du laboratoire : l'adresse 192.168.56.10 de la VM est annoncée comme point d'entrée du PoP, et seul l'hôte peut l'atteindre. La seconde interface, en NAT, fournit l'accès Internet nécessaire aux téléchargements sans être exposée aux clients.

La VM « sase-pop » a été créée avec les paramètres du tableau 4.02. À l'installation, j'ai choisi le profil minimal, activé le serveur OpenSSH et refusé les paquets snap supplémentaires. Après le premier redémarrage, j'ai fixé l'adresse de l'interface host-only avec Netplan (extrait 4.01), afin que l'adresse d'entrée du PoP, à laquelle le tunnel WireGuard est lié, ne change jamais. La liaison a été vérifiée par un ping puis par une connexion SSH depuis PowerShell, ce qui permet ensuite de travailler par copier-coller.

```yaml
network:
  version: 2
  ethernets:
    enp0s8:
      dhcp4: false
      addresses: [192.168.56.10/24]
```

*Extrait 4.01 — Adresse fixe de l'interface host-only (Netplan).*

### 4.5.2 Étapes 2 et 3 : socle logiciel, paramètres noyau et initialisation

Sur la VM, j'ai installé Docker Engine et le plugin Compose depuis les paquets Ubuntu (`docker.io`, `docker-compose-v2`), ainsi que `wireguard-tools`, `gettext-base` (pour `envsubst`), `openssl`, `oathtool` (calcul des codes TOTP sans téléphone), `jq` et `unzip`. Docker Engine natif est préféré à Docker Desktop pour la raison de mémoire exposée plus haut.

Trois réglages préparent la suite. Le paramètre noyau `net.netfilter.nf_log_all_netns=1`, associé au module `nf_log_syslog`, autorise les règles nftables situées dans l'espace réseau d'un conteneur à écrire dans le journal noyau de l'hôte : sans lui, les refus du FWaaS resteraient invisibles dans `kern.log` et donc dans Grafana. Un fichier d'échange de 2 Go constitue un filet de sécurité contre un dépassement mémoire. Enfin, le pare-feu de la VM (`ufw`) n'autorise que SSH (22/tcp) et WireGuard (51820/udp).

J'ai ensuite copié l'archive du dépôt sur la VM (`scp`) et exécuté le script d'initialisation `init.sh`, qui réalise quatre opérations :

- la **PKI du laboratoire** : une autorité racine (clé RSA de 4 096 bits) et un certificat joker `*.sase.lab` signé par elle, qui sert d'identité TLS commune à tous les services publiés ;
- les **secrets applicatifs** : secret partagé, secret de cookie et secret client de Pomerium tirés aléatoirement, ainsi que les mots de passe d'administration de Keycloak et de Grafana, écrits dans `.env` en droits 600 ;
- les **clés WireGuard** : sept paires de clés (PoP utilisateurs, deux tunnels du PoP, deux tunnels de l'équipement de succursale, home-laptop et mobile) et les profils clients correspondants ;
- le **rendu des modèles** : `config.yaml.tpl` (Pomerium) et `realm-sase.json.tpl` (Keycloak) sont instanciés par `envsubst`, de sorte que le même secret client figure des deux côtés.

```bash
# PKI : autorité racine + certificat joker *.sase.lab
openssl genrsa -out certs/ca.key 4096
openssl req -x509 -new -nodes -key certs/ca.key -sha256 -days 1095 \
  -subj "/C=MG/O=SASE-LAB/CN=SASE Lab Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" -out certs/ca.crt
openssl genrsa -out certs/sase-lab.key 2048
openssl req -new -key certs/sase-lab.key -subj "/C=MG/O=SASE-LAB/CN=*.sase.lab" \
  -out certs/sase-lab.csr
openssl x509 -req -in certs/sase-lab.csr -CA certs/ca.crt -CAkey certs/ca.key \
  -CAcreateserial -out certs/sase-lab.crt -days 397 -sha256 -extfile certs/san.ext

# Sept paires de clés, puis profil client (extrait)
gen() { local k; k=$(wg genkey); eval "${1}_PRIV=$k"; eval "${1}_PUB=$(echo "$k" | wg pubkey)"; }
for n in POP_ROAM POP_B1 POP_B2 EDGE_B1 EDGE_B2 HOME MOBILE; do gen $n; done
cat > clients/home-laptop.conf <<EOT
[Interface]
PrivateKey = $HOME_PRIV
Address = 10.100.0.11/32
DNS = 10.100.0.1
[Peer]
PublicKey = $POP_ROAM_PUB
Endpoint = 192.168.56.10:51820
AllowedIPs = 10.20.0.0/24, 10.100.0.1/32
PersistentKeepalive = 25
EOT
```

*Extrait 4.02 — Initialisation de la PKI, des clés WireGuard et du profil client.*

L'intérêt de ce script est la cohérence : une seule exécution produit les noms, certificats, secrets et clés qui doivent s'accorder entre Pomerium, Keycloak et WireGuard. Il est idempotent pour la PKI mais régénère secrets et clés à chaque exécution ; une réexécution oblige à réimporter les profils sur Windows et à recréer le conteneur Keycloak. Les clés privées, le fichier `.env` et la clé de l'autorité ne sont jamais reproduits dans ce mémoire.

### 4.5.3 Étape 4a : le nœud pop-gw, WireGuard et le FWaaS nftables

Le conteneur `pop-gw` est construit sur Debian 12 allégée avec WireGuard, nftables, iproute2 et iperf3. Il reçoit la seule capacité `NET_ADMIN`, active le routage IPv4, abaisse le seuil des ports non privilégiés à zéro pour que Pomerium puisse lier le port 443 dans cet espace réseau, et publie sur la VM le seul port UDP 51820. Il est rattaché aux quatre réseaux `svc`, `apps`, `wan1` et `wan2` avec l'adresse `.1` dans chacun.

```yaml
networks:
  svc:    {driver: bridge, ipam: {config: [{subnet: 10.20.0.0/24, gateway: 10.20.0.254}]}}
  apps:   {driver: bridge, internal: true,
           ipam: {config: [{subnet: 10.30.0.0/24, gateway: 10.30.0.254}]}}
  wan1:   {driver: bridge, internal: true,
           ipam: {config: [{subnet: 10.10.1.0/24, gateway: 10.10.1.254}]}}
  wan2:   {driver: bridge, internal: true,
           ipam: {config: [{subnet: 10.10.2.0/24, gateway: 10.10.2.254}]}}
  branch_lan: {driver: bridge, internal: true,
           ipam: {config: [{subnet: 192.168.10.0/24, gateway: 192.168.10.254}]}}

services:
  pop-gw:
    build: ./pop-gw
    cap_add: [NET_ADMIN]
    sysctls:
      net.ipv4.ip_forward: "1"
      net.ipv4.ip_unprivileged_port_start: "0"
    ports: ["51820:51820/udp"]
    networks:
      svc:  {ipv4_address: 10.20.0.1}
      apps: {ipv4_address: 10.30.0.1}
      wan1: {ipv4_address: 10.10.1.1}
      wan2: {ipv4_address: 10.10.2.1}
    volumes:
      - ./pop-gw/nftables.nft:/etc/sase/nftables.nft:ro
      - ./pop-gw/wireguard:/etc/wireguard-sase:ro

  pomerium:
    image: pomerium/pomerium:${POMERIUM_TAG:-v0.31.3}
    network_mode: "service:pop-gw"   # sidecar : partage 10.20.0.1
    depends_on: {pop-gw: {condition: service_healthy}}
```

*Extrait 4.03 — Orchestration : cinq réseaux, nœud PoP et services en pile réseau partagée.*

Son script d'entrée crée l'interface `wg0` (10.100.0.1/24, MTU 1380 pour absorber l'encapsulation) puis `wg-b1` et `wg-b2` (172.16.1.1/30 et 172.16.2.1/30) pour la succursale. Il charge ensuite le pare-feu, lance le serveur iperf3 des tests SD-WAN et l'agent SD-WAN du PoP, et crée le fichier `/run/pop-ready`. Ce fichier est lu par la sonde de santé du conteneur : les autres services ne démarrent qu'une fois le nœud réseau prêt.

```bash
ip link add wg0 type wireguard
wg setconf wg0 /etc/wireguard-sase/wg0.conf
ip addr add 10.100.0.1/24 dev wg0
ip link set wg0 up mtu 1380
for n in 1 2; do
  ip link add wg-b$n type wireguard
  wg setconf wg-b$n /etc/wireguard-sase/wg-b$n.conf
  ip addr add 172.16.$n.1/30 dev wg-b$n
  ip link set wg-b$n up mtu 1380
done
nft -f /etc/sase/nftables.nft
iperf3 -s -D -p 5201
/opt/sdwan-gw-agent.sh &
touch /run/pop-ready
```

*Extrait 4.04 — Entrée du PoP : création des trois interfaces et chargement du pare-feu.*

Côté WireGuard, chaque pair est identifié par sa clé publique et associé à une adresse en `/32`. Le profil du poste distant ne contient que deux routes (10.20.0.0/24 et 10.100.0.1/32), impose le DNS du PoP (10.100.0.1) et maintient la session par un keepalive de 25 secondes. Ce point est essentiel : aucune route vers 10.30.0.0/24 n'est annoncée aux clients.

Le pare-feu (extrait 4.05) applique une politique de refus par défaut. Les trois chaînes remplissent des rôles distincts :

- **INPUT** (trafic destiné au PoP) accepte l'établissement des tunnels (UDP 51820, et 51821 ou 51822 depuis l'adresse de l'équipement de succursale), puis uniquement depuis les interfaces de tunnel et les sous-réseaux d'utilisateurs : DNS (53), HTTPS (443), Keycloak (8443), proxy (3128), iperf3 (5201) et un ICMP limité à 10 paquets par seconde ;
- **FORWARD** (trafic traversant le PoP) n'autorise que les connexions déjà établies : aucun transit direct d'un tunnel vers le réseau 10.30.0.0/24, l'accès aux applications passant exclusivement par le ZTNA ;
- **OUTPUT** (trafic émis par le PoP) limite la sortie au web (80, 443), au DNS et au NTP, ainsi qu'aux réseaux privés.

Chaque refus est journalisé avec un préfixe explicite (`SASE-FW-INPUT-DROP`, `SASE-FW-FWD-DROP`, `SASE-FW-EGRESS-DROP`), limité à 20 entrées par seconde pour ne pas saturer le journal en cas de balayage de ports.

```nftables
table inet sase_fw {
  chain input {
    type filter hook input priority 0; policy drop;
    ct state invalid drop
    ct state established,related accept
    iifname "lo" accept
    udp dport 51820 accept comment "WG utilisateurs itinerants"
    ip saddr 10.10.1.2 udp dport 51821 accept comment "WG succursale lien 1"
    ip saddr 10.10.2.2 udp dport 51822 accept comment "WG succursale lien 2"
    iifname $TUNNELS ip saddr $USERS_NETS \
      tcp dport { 53, 443, 3128, 8443 } accept
    iifname $TUNNELS ip saddr $USERS_NETS udp dport 53 accept
    iifname $TUNNELS ip saddr $USERS_NETS icmp type echo-request \
      limit rate 10/second accept
    limit rate 20/second log prefix "SASE-FW-INPUT-DROP " counter drop
  }
  chain forward {
    type filter hook forward priority 0; policy drop;
    ct state invalid drop
    ct state established,related accept
    limit rate 20/second log prefix "SASE-FW-FWD-DROP " counter drop
  }
}
```

*Extrait 4.05 — Cœur de la politique nftables du PoP (table `inet sase_fw`, extrait).*

### 4.5.4 Étape 4b : identité et accès, Keycloak et Pomerium

Le royaume `sase` est importé au premier démarrage. Il définit quatre groupes (`employees`, `finance`, `it-admin`, `partners`), cinq comptes, la protection contre la force brute (verrouillage après cinq échecs), la journalisation des événements et un jeton d'accès de cinq minutes. Un client OIDC confidentiel nommé `pomerium` y est déclaré avec un seul URI de redirection, `https://authenticate.sase.lab/oauth2/callback`, et un mapper d'appartenance aux groupes qui place la liste des groupes dans la revendication `groups`. L'action requise `CONFIGURE_TOTP` est affectée à alice, bob, carol et dave : le second facteur est imposé à la première connexion. Eve n'en a pas, ce qui permet de comparer. Le tas Java est plafonné à 640 Mo et la base H2 locale est réservée au laboratoire.

```json
{
  "realm": "sase", "enabled": true,
  "bruteForceProtected": true, "failureFactor": 5,
  "accessTokenLifespan": 300, "eventsEnabled": true,
  "groups": [{"name":"employees"},{"name":"finance"},
             {"name":"it-admin"},{"name":"partners"}],
  "users": [
    {"username":"alice","groups":["/employees","/finance"],
     "credentials":[{"type":"password","value":"Alice#Lab2026"}],
     "requiredActions":["CONFIGURE_TOTP"]},
    {"username":"dave","groups":["/partners"],
     "credentials":[{"type":"password","value":"Dave#Lab2026"}],
     "requiredActions":["CONFIGURE_TOTP"]}
  ],
  "clients": [{
    "clientId":"pomerium", "protocol":"openid-connect", "publicClient":false,
    "secret":"${POMERIUM_CLIENT_SECRET}",
    "redirectUris":["https://authenticate.sase.lab/oauth2/callback"],
    "protocolMappers":[{"name":"groups","protocolMapper":"oidc-group-membership-mapper",
      "config":{"claim.name":"groups","full.path":"false","id.token.claim":"true",
                "access.token.claim":"true"}}]
  }]
}
```

*Extrait 4.06 — Royaume Keycloak : groupes, comptes, TOTP et mapper de groupes (extrait).*

Pomerium, dont le modèle `config.yaml.tpl` devient `config.yaml` après `envsubst`, définit l'URL du service d'authentification, le fournisseur OIDC (le royaume `sase` de Keycloak), les secrets et quatre routes (extrait 4.07) : `files` (groupes `employees` ou `partners`), `finance` (groupe `finance`), `admin` et `grafana` (groupe `it-admin`). Chaque route est refusée par défaut sauf si une règle `allow` correspond. La route `files` ne pointe pas directement sur CloudDrive : elle transmet la requête à mitmproxy (`127.0.0.1:8081`) et active `pass_identity_headers`, qui ajoute l'assertion JWT signée dans l'en-tête `X-Pomerium-Jwt-Assertion`. C'est ce jeton qui permet au CASB d'appliquer des règles par groupe. La variable `SSL_CERT_FILE` fait approuver au conteneur l'autorité du laboratoire, condition pour joindre Keycloak en HTTPS.

```yaml
address: ":443"
authenticate_service_url: https://authenticate.sase.lab
certificate_file: /certs/sase-lab.crt
certificate_key_file: /certs/sase-lab.key
idp_provider: oidc
idp_provider_url: https://idp.sase.lab:8443/realms/sase
idp_client_id: pomerium
idp_client_secret: ${POMERIUM_CLIENT_SECRET}
routes:
  - from: https://files.sase.lab
    to: http://127.0.0.1:8081          # passage par le CASB/DLP
    pass_identity_headers: true
    policy:
      - allow:
          or:
            - claim/groups: employees
            - claim/groups: partners
  - from: https://finance.sase.lab
    to: http://10.30.0.22:80
    policy:
      - allow:
          and:
            - claim/groups: finance
```

*Extrait 4.07 — Politique Pomerium : routes, refus par défaut et identité propagée.*

Une limite doit être signalée dès maintenant : l'add-on CASB décode l'assertion JWT sans en vérifier la signature. Ce choix est acceptable ici parce que le port 8081 n'écoute que sur la boucle locale et que le pare-feu en interdit l'accès depuis les tunnels, mais il devrait être corrigé en production.

Le tableau 4.07 rassemble la matrice des droits effectivement configurée. Elle sert de référence aux scénarios de la section 4.7.

| Ressource | alice (employees, finance) | bob (employees, it-admin) | carol (employees) | dave (partners) | eve (aucun) |
|:--|:--|:--|:--|:--|:--|
| CloudDrive | lecture-écriture | lecture-écriture | lecture-écriture | lecture seule | refus |
| Finance | autorisé | refus | refus | refus | refus |
| Admin IT | refus | autorisé | refus | refus | refus |
| Grafana | refus | autorisé | refus | refus | refus |

: Tableau 4.07 — Matrice des droits des comptes de démonstration

### 4.5.5 Étape 4c : contrôle web et DNS, Squid et dnsmasq

dnsmasq résout les noms du laboratoire et neutralise les destinations interdites. La zone `sase.lab` est résolue en 10.20.0.1, de sorte que toutes les applications ZTNA pointent vers le PoP ; la zone `inet.lab` est résolue vers le serveur d'Internet simulé (10.20.0.70). Les noms de la liste de blocage (`malware.inet.lab`, `phishing.inet.lab`, `casino.inet.lab`, `bet365.com`) sont résolus en `0.0.0.0` : c'est un puits DNS (*sinkhole*) qui agit avant l'établissement de la connexion. Les autres noms sont transmis à des résolveurs publics.

```ini
# dnsmasq.conf
no-resolv
server=1.1.1.1
server=9.9.9.9
bind-dynamic
log-queries
log-facility=/var/log/dnsmasq/dnsmasq.log
address=/sase.lab/10.20.0.1
address=/inet.lab/10.20.0.70
conf-file=/etc/dnsmasq.d/blocklist.conf

# blocklist.conf
address=/malware.inet.lab/0.0.0.0
address=/phishing.inet.lab/0.0.0.0
address=/casino.inet.lab/0.0.0.0
address=/bet365.com/0.0.0.0
```

*Extrait 4.08 — Résolution des zones du laboratoire et puits DNS.*

Squid, en proxy explicite sur le port 3128, applique ses règles dans l'ordre (extrait 4.09). Il refuse d'abord les ports non sûrs et les méthodes `CONNECT` hors port 443, puis les domaines, les motifs d'URL et les extensions listés, avant d'autoriser les sources du tunnel utilisateur et de la succursale. La liste des domaines couvre les réseaux sociaux, les jeux d'argent, le stockage cloud non approuvé (Dropbox, WeTransfer, Mega), qui sert de détection de *Shadow IT*, et les sites de malware et d'hameçonnage de démonstration. Le cache est désactivé pour économiser la mémoire. Sans interception TLS (`ssl_bump` n'est pas activé), le filtrage HTTPS se limite au nom d'hôte visible dans la requête `CONNECT`.

```squid
http_port 3128
acl users src 10.100.0.0/24 192.168.10.0/24
acl blocked_domains dstdomain "/etc/squid/blocked_domains.txt"
acl blocked_urls url_regex -i "/etc/squid/blocked_urls.txt"
acl blocked_ext urlpath_regex -i \.(exe|msi|scr|bat)$
http_access deny !Safe_ports
http_access deny CONNECT !SSL_ports
http_access deny blocked_domains
http_access deny blocked_urls
http_access deny blocked_ext
http_access allow users
http_access deny all
cache deny all
access_log stdio:/var/log/squid/access.log squid
forwarded_for delete
```

*Extrait 4.09 — Règles d'accès du SWG Squid (extrait).*

### 4.5.6 Étape 4d : CASB et DLP avec mitmproxy

mitmproxy fonctionne en reverse proxy (`reverse:http://10.30.0.21:5000@8081`) et n'écoute que sur `127.0.0.1` : il ne peut être atteint que depuis la pile réseau du PoP, c'est-à-dire par Pomerium. Son add-on Python `casb_dlp.py` traite chaque requête en quatre temps : il extrait l'identité et les groupes du JWT, classe l'opération (consultation, téléversement, téléchargement, partage ou suppression), applique dans l'ordre les règles CASB du fichier `policy.json`, puis, pour un téléversement de 10 Mo au plus, soumet le contenu au moteur DLP. La décision est `allow`, `block` (réponse 403 avec la règle déclenchée) ou `alert`, et chaque événement est écrit en JSON dans `events.jsonl` avec l'horodatage, l'identité, l'action, le fichier, la règle et la décision.

```json
{
  "app": "CloudDrive", "sanctioned": true,
  "rules": [
    {"id":"CASB-01","description":"Partenaires externes : lecture seule",
     "groups_any":["partners"],"actions":["upload","delete","share"],"decision":"block"},
    {"id":"CASB-02","description":"Partage public reserve au groupe it-admin",
     "not_groups_any":["it-admin"],"actions":["share"],"decision":"block"},
    {"id":"CASB-03","description":"Extensions executables interdites",
     "actions":["upload"],"filename_ext":[".exe",".bat",".ps1",".scr",".msi"],
     "decision":"block"}
  ],
  "dlp": {"block":["CARTE_BANCAIRE","IBAN_FR","NIR_FR","EICAR_TEST","CLE_AWS"],
          "alert":["MOT_CLE_CONFIDENTIEL"]}
}
```

*Extrait 4.10 — Politique CASB et catégories DLP.*

Le moteur `dlp_engine.py` ne se contente pas d'expressions régulières. Pour limiter les faux positifs, il valide les candidats par un contrôle de cohérence : algorithme de Luhn pour les numéros de carte, modulo 97 pour les IBAN français, clé de contrôle pour le NIR. Il reconnaît aussi un motif de clé AWS, la chaîne de test EICAR et quelques mots-clés de confidentialité. Les données détectées ne sont pas recopiées dans les journaux : seuls les compteurs par catégorie le sont.

```python
RX_CARD  = re.compile(rb"(?<!\d)(\d(?:[ -]?\d){12,18})(?!\d)")
RX_IBAN  = re.compile(rb"\bFR\d{2}(?: ?[0-9A-Z]{4}){5} ?[0-9A-Z]{3}\b")
RX_NIR   = re.compile(rb"(?<!\d)([12]) ?(\d{2}) ?(0[1-9]|1[0-2]) ?(\d{2}) ?(\d{3}) ?(\d{3}) ?(\d{2})(?!\d)")
RX_AWS   = re.compile(rb"AKIA[0-9A-Z]{16}")

def luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2
            d = d - 9 if d > 9 else d
        total += d
        alt = not alt
    return total % 10 == 0

def scan(data: bytes) -> dict:
    found = {}
    n = sum(1 for m in RX_CARD.finditer(data)
            if luhn_ok(re.sub(rb"\D", b"", m.group(1)).decode()))
    if n: found["CARTE_BANCAIRE"] = n
    ...
    return found
```

*Extrait 4.11 — Détection DLP validée par algorithmes (Luhn, IBAN, NIR).*

CloudDrive, l'application protégée, est une petite application Flask de dépôt de fichiers qui affiche l'identité et les groupes lus dans le JWT. Le tableau 4.08 rassemble les règles configurées.

| Règle | Objet contrôlé | Décision |
|:--|:--|:--|
| CASB-01 | Groupe partners : téléversement, suppression, partage | Bloquer (lecture seule) |
| CASB-02 | Partage public pour tout compte hors du groupe it-admin | Bloquer |
| CASB-03 | Téléversement d'extensions exécutables (.exe, .bat, .ps1, .scr, .msi) | Bloquer |
| DLP-CARTE_BANCAIRE | Numéro de carte valide (contrôle de Luhn) | Bloquer |
| DLP-IBAN_FR | IBAN français valide (modulo 97) | Bloquer |
| DLP-NIR_FR | NIR français valide (clé de contrôle) | Bloquer |
| DLP-CLE_AWS, DLP-EICAR_TEST | Motif de clé AWS ; chaîne de test EICAR | Bloquer |
| DLP-MOT_CLE_CONFIDENTIEL | Mots-clés de confidentialité | Alerter, sans bloquer |

: Tableau 4.08 — Règles CASB et DLP configurées

### 4.5.7 Étape 4e : SD-WAN, politique centrale et agents

Le SD-WAN relie le LAN de la succursale au PoP par deux tunnels WireGuard, `wg-b1` porté par `wan1` et `wg-b2` porté par `wan2`. À l'équipement `branch-edge`, des règles nftables posent une marque sur chaque paquet selon sa classe : la classe *business* (TCP 443, 3128, 8443 et DNS) reçoit la marque 1, la classe *temps réel* (UDP 5060 et 5201) la marque 2, et tout le reste est de la classe *bulk*. Les règles `ip rule` associent la marque 1 à la table 101 et la marque 2 à la table 102 ; la route par défaut, qui sert la classe *bulk*, passe par `wg-b2`.

```bash
# Classification applicative (branch-edge)
nft add rule ip sdwan pre tcp dport '{ 443, 3128, 8443 }' meta mark set 1
nft add rule ip sdwan pre udp dport 53 meta mark set 1
nft add rule ip sdwan pre udp dport '{ 5060, 5201 }' meta mark set 2
ip rule add fwmark 1 lookup 101 pref 101
ip rule add fwmark 2 lookup 102 pref 102

# Politique centrale (lue par l'edge ET par le PoP)
PROBE_COUNT=3     # paquets ICMP par mesure
INTERVAL=2        # secondes entre deux cycles
RTT_MAX=120       # ms : au-dela, lien degrade
LOSS_MAX=20       # % de perte : au-dela, lien degrade
BUSINESS_PREF=1   # classe business : prefere wg-b1
BULK_PREF=2       # classe bulk : prefere wg-b2
```

*Extrait 4.12 — Classification par marques, routage par politique et politique SLA centrale.*

Un agent mesure toutes les deux secondes, par trois sondes ICMP, la perte et le RTT de chaque tunnel. Un lien est déclaré dégradé si la perte dépasse 20 % ou si le RTT dépasse 120 ms. La classe *business* préfère `wg-b1` et bascule sur `wg-b2` si son lien préféré est dégradé ; la classe *bulk* fait l'inverse ; la classe *temps réel* choisit toujours le lien au meilleur score, défini par `RTT + 20 × perte`, la perte étant exprimée en pourcentage. Un agent symétrique côté PoP choisit le tunnel de retour vers 192.168.10.0/24. Les seuils et les préférences sont réunis dans un fichier unique lu par les deux extrémités, qui tient lieu de contrôleur central. Un petit outil, `impair`, injecte sur un lien simulé un délai de 250 ms et 30 % de perte (netem) pour provoquer les bascules.

```bash
pick_pref() { # tunnel prefere, bascule sur l'autre s'il est degrade
  local p=$1 o=$((3 - $1))
  if [ "${H[$p]}" = 1 ]; then echo "$p"
  elif [ "${H[$o]}" = 1 ]; then echo "$o"
  else echo "$p"; fi
}
pick_best() { # meilleur score RTT + 20 x perte
  local s1=$(( R[1] + L[1] * 20 )) s2=$(( R[2] + L[2] * 20 ))
  if [ "${H[1]}" = 1 ] && [ "${H[2]}" = 1 ]; then
    [ "$s1" -le "$s2" ] && echo 1 || echo 2
  elif [ "${H[1]}" = 1 ]; then echo 1
  elif [ "${H[2]}" = 1 ]; then echo 2
  else [ "$s1" -le "$s2" ] && echo 1 || echo 2; fi
}
apply business 101 "$(pick_pref "$BUSINESS_PREF")"
apply realtime 102 "$(pick_best)"
apply bulk main "$(pick_pref "$BULK_PREF")"
```

*Extrait 4.13 — Sélection de chemin par classe dans l'agent SD-WAN (extrait).*

Je classe cette fonction au niveau N2 : les tunnels multi-chemins, la mesure du SLA, le routage par politique et la bascule automatique sont réels, mais le contrôleur est un fichier partagé, le routage dynamique est absent et l'agent n'implémente pas d'hystérésis.

### 4.5.8 Étape 4f : supervision, Fluent Bit, Loki et Grafana

Fluent Bit collecte les journaux par deux voies : le pilote de journalisation Docker `fluentd`, qui lui envoie ceux de Keycloak et de Pomerium, et la lecture de fichiers (journal d'accès de Squid, journal de dnsmasq, événements CASB, journaux SD-WAN et `kern.log` de l'hôte, filtré sur le préfixe `SASE-FW`). Chaque flux reçoit une étiquette `component` (`ztna`, `iam`, `squid`, `dns`, `casb`, `sdwan`, `firewall`) et est envoyé à Loki (10.20.0.61). Loki stocke sur le système de fichiers avec un index minimal ; Grafana, dont la source de données est provisionnée, interroge Loki en LogQL.

```ini
[INPUT]
  Name tail
  Path /logs/squid/access.log
  Tag  squid
[INPUT]
  Name tail
  Path /logs/casb/events.jsonl
  Tag  casb
[INPUT]
  Name tail
  Path /hostlog/kern.log
  Tag  fw
[FILTER]
  Name  grep
  Match fw
  Regex log SASE-FW
[OUTPUT]
  Name   loki
  Match  squid
  Host   10.20.0.61
  Port   3100
  Labels job=sase,component=squid
```

*Extrait 4.14 — Collecte Fluent Bit et routage vers Loki (extrait).*

Grafana est lui-même publié par Pomerium et réservé au groupe `it-admin` : l'outil de supervision n'est pas exposé à tous les utilisateurs, ce qui est essentiel puisque les journaux révèlent des identités, des usages et l'architecture interne. Le format exact des journaux Pomerium et Keycloak dépend de la version déployée ; les requêtes LogQL ont été ajustées à ce qui est observé.

### 4.5.9 Étapes 5 et 6 : construction, démarrage ordonné et vérifications du PoP

Le démarrage suit un ordre qui respecte les dépendances (extrait 4.15). Les services de supervision d'abord, parce que les journaux Docker sont envoyés à Fluent Bit dès leur création ; puis `pop-gw`, qui fournit la pile réseau, avec le DNS et Squid ; puis Keycloak, dont l'import du royaume demande 40 à 90 secondes ; ensuite les applications, puis le CASB, qui doit écouter avant la première requête ; Pomerium en dernier ; enfin la succursale.

```bash
docker compose pull && docker compose build
docker compose up -d loki fluent-bit grafana
docker compose up -d pop-gw dns squid
docker compose up -d keycloak
docker compose up -d clouddrive finance admin inet-sim
docker compose up -d casb-dlp
docker compose up -d pomerium
docker compose up -d branch-edge branch-pc
```

*Extrait 4.15 — Ordre de démarrage de la maquette.*

Les vérifications côté PoP portent sur quatre points : les trois interfaces WireGuard (`wg0`, `wg-b1`, `wg-b2`) sont présentes, le jeu de règles contient la table `sase_fw` avec ses trois chaînes, le point de découverte OIDC de Keycloak renvoie un document dont l'émetteur est `https://idp.sase.lab:8443/realms/sase`, et Pomerium répond sur le port 443. Tous les services sont en cours d'exécution et `pop-gw` est déclaré sain par sa sonde.

```bash
docker exec pop-gw wg show
docker exec pop-gw nft list ruleset | head -n 40
docker run --rm --network container:pop-gw curlimages/curl -sk \
  https://10.20.0.1:8443/realms/sase/.well-known/openid-configuration | head -c 120
docker stats --no-stream
free -m
```

*Extrait 4.16 — Commandes de vérification du PoP.*

### 4.5.10 Étapes 7 et 8 : le poste distant Windows et la succursale

**Poste distant.** J'ai copié depuis la VM le profil `home-laptop.conf` et le certificat de l'autorité, importé le tunnel dans WireGuard sans l'activer, puis approuvé l'autorité du laboratoire dans les autorités racines de Windows (`certutil -addstore -f Root`). J'ai ajouté au fichier `hosts` les noms `idp`, `authenticate`, `files`, `finance`, `admin` et `grafana` du domaine `sase.lab`, ce qui garantit la résolution même si Windows ignore le DNS du tunnel. Enfin, j'ai créé un profil Edge dédié qui utilise le proxy SWG (`--proxy-server=http://10.20.0.1:3128`) et en exclut le domaine `sase.lab` (`--proxy-bypass-list=*.sase.lab`) : les applications privées vont directement à Pomerium, tout le reste passe par Squid. Une fois le tunnel activé, quatre contrôles valident la chaîne réseau : le ping de 10.20.0.1, la résolution de `files.sase.lab` en 10.20.0.1, celle de `malware.inet.lab` en `0.0.0.0` et une requête `curl -I https://files.sase.lab`, qui doit renvoyer une redirection 302 vers le service d'authentification.

**Succursale.** L'équipement `branch-edge` ouvre ses deux tunnels, installe le classifieur nftables, les règles de routage par politique et lance l'agent SLA ; `branch-pc` utilise `branch-edge` comme passerelle et le PoP comme DNS. Les routes autorisées pour l'équipement se limitent à 10.20.0.0/24 et aux adresses de tunnel. J'ai vérifié que les deux interfaces présentent un dernier handshake, que les règles `fwmark 1` vers la table 101 et `fwmark 2` vers la table 102 sont en place, que le journal de l'agent indique `classe=business chemin=wg-b1` et `classe=bulk chemin=wg-b2`, et que le ping et la résolution DNS aboutissent depuis `branch-pc`.

### 4.5.11 Étapes 9 et 10 : première connexion et sécurisation

La première connexion valide l'intégration de bout en bout. Dans le profil Edge dédié, tunnel actif, j'ai ouvert `https://files.sase.lab` : le navigateur est redirigé vers Keycloak. Je me suis connecté avec alice ; Keycloak impose alors la configuration du TOTP. J'ai choisi l'option sans lecture de QR code pour obtenir la clé secrète et calculé le code depuis la VM avec `oathtool`. La page CloudDrive s'est affichée avec l'identité et les groupes d'alice : la chaîne IAM, ZTNA, CASB puis application fonctionne. Un affichage « anonyme » sans groupes aurait signalé que l'en-tête JWT n'est pas transmis ou que le mapper de groupes est absent.

La sécurisation de l'infrastructure complète la réalisation par six principes :

- **exposition minimale** : seul le port UDP 51820 est publié ; Keycloak, Pomerium, Squid et le DNS ne sont joignables que depuis un tunnel, et `ufw` limite l'hôte à SSH et WireGuard ;
- **secrets** : `.env` et les fichiers `.conf` en droits 600, générés aléatoirement ; la clé privée de l'autorité n'est utile qu'à l'émission des certificats et doit quitter la VM après l'initialisation ;
- **moindre privilège** : la capacité `NET_ADMIN` est réservée à `pop-gw` et à la succursale, aucun socket Docker n'est monté et les montages sont en lecture seule ;
- **segmentation** : réseau des applications interne, FORWARD en refus par défaut, équipement de succursale limité à 10.20.0.0/24 ;
- **identité** : MFA par TOTP, verrouillage après cinq échecs, jeton de cinq minutes, compte d'administration Keycloak distinct (`kcadmin`) ;
- **mises à jour** : tags d'images épinglés et retest après chaque changement de version.

## 4.6 Cheminement d'une connexion et chaîne de confiance

Le parcours d'une requête depuis le poste distant jusqu'à CloudDrive distingue deux plans : le plan de transport, qui permet au paquet d'atteindre le PoP, et le plan de contrôle d'accès, qui décide si la requête applicative peut être transmise. Le tableau 4.09 reprend les neuf étapes observées.

| Étape | Action | Composant | Preuve / journal |
|:--|:--|:--|:--|
| 1 | Établissement du tunnel à partir de la clé privée de l'appareil | WireGuard `wg0` | `wg show`, handshake |
| 2 | Filtrage du paquet entrant, seuls les services du PoP sont exposés | nftables INPUT | `SASE-FW-INPUT-DROP` |
| 3 | Résolution de `files.sase.lab` vers 10.20.0.1 | dnsmasq | journal DNS |
| 4 | Requête HTTPS sans session : redirection vers l'IdP | Pomerium :443 | 302 vers `authenticate` |
| 5 | Mot de passe puis code TOTP ; émission du jeton OIDC | Keycloak :8443 | `LOGIN`, groupes |
| 6 | Évaluation de la politique de la route (claim/groups) | Pomerium | 403 ou passage |
| 7 | Relais vers le CASB avec le JWT d'identité | mitmproxy :8081 | en-tête `X-Pomerium-Jwt-Assertion` |
| 8 | Contrôle de l'action, puis inspection DLP du contenu | `casb_dlp.py`, `dlp_engine.py` | `events.jsonl` |
| 9 | Transmission à l'application du réseau `apps` | CloudDrive 10.30.0.21 | journal applicatif |

: Tableau 4.09 — Cheminement d'une connexion et traces produites à chaque étape

La navigation web suit un chemin parallèle : navigateur, dnsmasq, Squid, puis Internet ou l'Internet simulé. Aucune authentification n'est configurée sur Squid ; les décisions du SWG reposent donc sur les domaines, les URL visibles et les caractéristiques de la requête, et non sur les groupes Keycloak. C'est une limite de la maquette, reprise à la section 4.9.2.

Cette architecture permet de distinguer plusieurs catégories d'échec, ce qui est décisif pour interpréter les observations : une absence de tunnel relève du transport ; une erreur de certificat ou de résolution empêche d'atteindre le service ; un échec de connexion concerne la preuve d'identité ; un code 403 de Pomerium traduit une décision d'autorisation négative ; un refus CASB ou DLP intervient après l'accès à l'application, au moment d'une opération donnée. Un résultat négatif n'est pas en soi une preuve de sécurité : il peut aussi provenir d'une panne ou d'une mauvaise configuration.

## 4.7 Validation fonctionnelle par scénarios

Les scénarios vérifient des propriétés distinctes de l'architecture, puis leur enchaînement. Chacun associe une précondition, une action, un résultat observable et une trace technique. Ils mobilisent cinq profils d'identité et quatre ressources. Toutes les données de test sont fictives : carte bancaire d'essai publique, IBAN et NIR d'exemple, fichier de test EICAR.

**S1 — accès sécurisé d'un utilisateur distant.** Tunnel actif, j'ai contrôlé que 10.20.0.1 répond au ping et que `curl.exe -I https://files.sase.lab` renvoie une redirection 302. Dans le profil Edge dédié, j'ai ouvert `files.sase.lab`, saisi le mot de passe d'alice puis le code TOTP, et obtenu la page CloudDrive affichant l'identité et les groupes. Le même test depuis le LAN de la succursale (`branch-pc`) renvoie la même redirection 302 : aucune confiance n'est liée à l'emplacement. Trois contrôles successifs sont observés : l'identité de l'appareil (clé WireGuard), l'identité de l'utilisateur avec second facteur (Keycloak) et l'autorisation par groupe (Pomerium).

**S2 et S3 — accès non autorisé et démonstration Zero Trust.** Sans tunnel, aucun service n'est joignable ; avec un tunnel mais une identité inconnue ou un mauvais mot de passe, Keycloak refuse la connexion et verrouille temporairement le compte après cinq échecs ; un appareil dont la clé n'est pas enregistrée n'obtient aucun handshake. Le refus intervient donc avant l'application, d'abord au niveau réseau, puis à celui de l'appareil, enfin à celui de l'identité. Le scénario S3 prouve qu'une authentification réussie ne suffit pas : connecté en carol (groupe `employees`) avec TOTP, j'ai ouvert `finance.sase.lab` et obtenu une page 403 alors que la session était valide. Le même contrôle a été mené avec les autres comptes selon la matrice du tableau 4.07. Le code 403 matérialise un refus d'autorisation ; il se distingue d'un échec d'authentification, d'une erreur DNS ou d'une indisponibilité de l'amont.

**S4 — FWaaS.** Tunnel actif, j'ai testé trois ports du PoP depuis PowerShell. Le port 443 est joignable ; les ports 22 et 8081 ne le sont pas, tandis que le ping reste possible puisque l'ICMP limité est autorisé. Le paquet refusé est supprimé sans réponse, d'où le délai dépassé. Le journal noyau de la VM contient les lignes correspondantes : préfixe `SASE-FW-INPUT-DROP`, interface `wg0`, source 10.100.0.11, destination 10.20.0.1 et ports de destination 22 et 8081. Le port 8081, celui du CASB, est ainsi inaccessible depuis les clients, ce qui conforte l'hypothèse de confiance faite sur l'assertion JWT.

**S5 — SWG.** Depuis `branch-pc`, j'ai soumis à Squid six requêtes représentatives. La destination simulée `news.inet.lab` est autorisée (200) ; le même site avec le chemin `/gambling/` est refusé par le motif d'URL (403) ; un fichier `update.exe` l'est par l'extension (403) ; `casino.inet.lab` l'est par le domaine (403) ; l'accès HTTPS à `www.facebook.com` est refusé dès la requête `CONNECT` (403). Côté DNS, `malware.inet.lab` est résolu en `0.0.0.0` et `news.inet.lab` en 10.20.0.70. Trois mécanismes complémentaires sont ainsi observés : le puits DNS, le filtrage de domaine, d'URL et d'extension par Squid, et un filtrage HTTPS limité au domaine via `CONNECT`.

**S6 — CASB.** Le scénario exerce les règles du tableau 4.08 avec trois comptes dans CloudDrive, puis vérifie la détection de *Shadow IT* par Squid. Chaque action produit une ligne JSON avec l'utilisateur, ses groupes, l'action, le fichier, la décision et la règle. alice téléverse `propre.txt` (autorisé) mais ne peut pas partager (CASB-02) ; bob partage (groupe `it-admin`) mais ne peut pas téléverser `outil.exe` (CASB-03) ; dave consulte et télécharge (lecture seule) mais ne peut ni téléverser ni supprimer (CASB-01) ; l'accès à Dropbox est bloqué par le SWG. La visibilité provient du reverse proxy, qui voit chaque action applicative, et de l'identité du JWT ; le contrôle est granulaire (action, groupe et extension).

**S7 — DLP.** J'ai téléversé successivement dans CloudDrive, avec le compte alice, les six fichiers fictifs générés par le script de test. Les fichiers contenant une carte bancaire, un IBAN, un NIR ou la chaîne EICAR sont bloqués ; la note confidentielle déclenche une alerte sans blocage ; le fichier propre est accepté. Le moteur détecte des motifs validés par des algorithmes de contrôle, ce qui évite les faux positifs sur de simples suites de chiffres.

**S8 — SD-WAN.** J'ai suivi les décisions de l'agent dans son journal, relevé les tables de routage de référence (table 101 par `wg-b1`, table 102 au meilleur score, route par défaut par `wg-b2`), puis généré du trafic de test depuis `branch-pc` : un ping vers le PoP et un flux UDP iperf3 de 1 Mbit/s pendant 120 secondes, de la classe temps réel. Les deux compteurs de transmission sont du même ordre de grandeur (environ 1,5 Mo chacun). Cette lecture demande de la prudence : ils sont cumulés depuis la création des interfaces et incluent les sondes SLA envoyées toutes les deux secondes sur chaque tunnel ainsi que les keepalives. Ils prouvent que les deux tunnels sont actifs, mais ne suffisent pas à attribuer une classe à un tunnel ; cette attribution repose sur les tables de routage et sur le journal de l'agent.

**S9 — supervision centralisée.** Connecté en bob, j'ai ouvert Grafana par Pomerium, vérifié dans Explore que les sept composants attendus remontent des événements et construit le tableau de bord « SASE — vue d'ensemble ». La valeur de la centralisation tient à la corrélation par horodatage et par identité, qui permet de reconstituer un incident de bout en bout. L'ensemble reste une solution de journalisation, non un SIEM : il manque la normalisation, les règles de détection multi-événements, la rétention longue et l'intégrité des journaux.

Le tableau 4.10 synthétise le niveau atteint et la preuve associée. Un niveau N1 n'est revendiqué que lorsqu'une preuve d'exécution existe.

| Composante | Outil | Niveau | Preuve |
|:--|:--|:--|:--|
| IAM et MFA | Keycloak | N1 | Écran TOTP et identité affichée (S1) ; verrouillage (S2) |
| ZTNA sans agent | Pomerium | N1 | Refus 403 de carol sur Finance (S3) |
| ZTNA par appareil | WireGuard (clé par pair) | N2 | Tests de ports (S4) ; pas de posture réelle |
| FWaaS | nftables | N2 | Tests de ports et journaux SASE-FW (S4) |
| SWG et DNS | Squid, dnsmasq | N1 (HTTP, DNS), N2 (HTTPS) | Codes HTTP et résolutions (S5) |
| CASB | mitmproxy et `policy.json` | N2 | Décisions CASB-01 à 03 (S6) |
| DLP | `dlp_engine.py` | N2 | Blocage carte bancaire et tableau des fichiers (S7) |
| SD-WAN | WireGuard, nftables, agents | N2 | Compteurs et journal de bascule (S8) |
| Supervision | Fluent Bit, Loki, Grafana | N1 | Sept sources, tableau de bord (S9) |
| Segmentation | Réseaux Docker, nftables | N1 | Compteurs de la chaîne forward (S4) |
| PoP mondial, élasticité, CASB par API, inspection TLS | — | N3 | Hors périmètre de la maquette |

: Tableau 4.10 — Niveau de réalisation et preuve par composante SASE

## 4.8 Performances, ressources et reprise

### 4.8.1 Empreinte en ressources

La mémoire doit être lue à deux niveaux : celle consommée par les conteneurs et celle effectivement disponible dans la VM. Le cache du système, les processus de l'hôte et les allocations de VirtualBox expliquent qu'une somme de conteneurs ne soit pas égale à la mémoire occupée par la VM. Le tableau 4.11 compare les estimations de dimensionnement aux valeurs mesurées à l'état stable, cinq minutes après le démarrage.

| Composant ou indicateur | Estimation (Mo) | Valeur mesurée (Mo) |
|:--|:--|:--|
| Keycloak | 600 à 800 | 629,1 |
| Pomerium | 120 à 200 | 59,97 |
| mitmproxy (CASB et DLP) | 100 à 150 | 17,89 |
| Squid et dnsmasq | 50 à 90 | 5,75 |
| Loki, Fluent Bit et Grafana | 300 à 450 | 150 |
| Mémoire utilisée dans la VM (hors cache) | 1 700 à 2 100 | 1 774 |
| Mémoire disponible dans la VM | plus de 800 attendu | 1 001 |

: Tableau 4.11 — Estimations et mesures de consommation mémoire

Les composants légers consomment sensiblement moins que prévu : Pomerium (environ 60 Mo) et mitmproxy (environ 18 Mo) sont sous leurs plages d'estimation, ce qui est cohérent avec des mesures prises hors charge. Keycloak, dont le tas est plafonné, reste dans la plage annoncée (629 Mo) et demeure le composant dominant. Au niveau de la VM, 1 774 Mo sont utilisés, dans la plage de 1,7 à 2,1 Go prévue au dimensionnement, et environ 1 Go reste disponible, ce qui satisfait le critère de plus de 800 Mo. Le fichier d'échange est toutefois sollicité (407 Mo sur 2 679 Mo) et la mémoire libre stricte est faible (130 Mo, le reste étant du cache) : la marge existe mais elle est étroite, ce qui justifie l'ordre de démarrage et l'arrêt des services non utilisés pendant les mesures.

L'hypothèse H9 du chapitre 3 fixe une borne de 2 422 Mo pour la somme mémoire des conteneurs. Les valeurs relevées (de l'ordre de 0,9 Go pour les cinq groupes mesurés) respectent cette borne. Le total ne peut en revanche être comparé à la plage de référence qu'une fois le périmètre de mesure identique (tous les conteneurs actifs, même métrique) ; la conclusion sur H9 est donc subordonnée à ce contrôle.

### 4.8.2 Latence et comportement des files d'attente

Le surcoût de la chaîne SASE s'évalue en comparant, dans des conditions identiques, le temps de réponse direct de l'application (requête émise depuis la pile réseau du PoP vers CloudDrive, 10.30.0.21:5000) et celui obtenu en traversant la chaîne de contrôle. Le protocole retient dix répétitions par condition ; la médiane décrit la tendance centrale et l'écart interquartile la dispersion. L'essai est répété sous trois niveaux de charge (faible, moyenne, élevée) pour relier les mesures au modèle de files d'attente.

Le surcoût relatif s'écrit :

$$\Delta T = \frac{T_{SASE} - T_{direct}}{T_{direct}} \times 100$$

Les modèles décrivent un comportement moyen sous hypothèses et ne remplacent pas les mesures. Le modèle M/M/1 décrit un composant à temps de service exponentiel ; le modèle M/G/1 convient mieux à l'inspection CASB et DLP, dont le temps de service varie avec la taille du contenu :

$$M/M/1 : \rho = \lambda/\mu \quad ( \rho < 1 ), \quad W = \frac{1}{\mu - \lambda}$$

$$M/G/1 : W = E[S] + \frac{\lambda \, E[S^2]}{2(1-\rho)}$$

L'hypothèse H4 n'est acceptée que si les taux d'utilisation mesurés restent inférieurs à 1 et si l'écart entre le surcoût expérimental et la prédiction demeure dans la tolérance de 30 % ; l'hypothèse H5 compare l'utilisation du processeur observée à l'approximation $U_i = \lambda_i S_i$, avec une tolérance de cinq points. Les valeurs numériques de cette campagne sont consignées dans le cahier de tests : elles dépendent de la charge injectée et ne peuvent être transposées à un débit de production.

### 4.8.3 Disponibilité et temps de reprise

La disponibilité théorique d'un composant est $A = MTBF/(MTBF + MTTR)$. Pour une chaîne de services en série, la disponibilité globale est le produit des disponibilités individuelles si les défaillances sont indépendantes et si tous les composants sont indispensables. Cette hypothèse est simplificatrice ici : plusieurs fonctions partagent la même VM et la même passerelle, et une panne de l'hôte ou de `pop-gw` provoque une indisponibilité commune.

Pour H6, la médiane du temps de bascule SD-WAN est comparée aux intervalles prédits au chapitre 3 : 1,4 à 4 s pour une coupure franche et 2,5 à 5 s pour une perte de 30 %. La fenêtre de 6 à 10 s annoncée par le cahier de réalisation est une valeur de conception, qui découle de l'intervalle de 2 s et des trois sondes de l'agent. Les deux ne sont pas directement conciliables sans définir le temps de bascule : je le mesure comme l'écart entre l'instant d'application de `impair` et l'horodatage de la ligne de changement de chemin dans le journal de l'agent, puis je confronte séparément cette mesure aux deux prédictions. Le temps de reprise après redémarrage du conteneur Keycloak est mesuré de la même façon, entre l'arrêt et le retour du point de découverte OIDC.

## 4.9 Bilan, limites et perspectives

### 4.9.1 Bilan par composante

Le tableau 4.12 rapproche chaque fonction SASE de l'outil qui la réalise, du niveau de réalisation et de la preuve disponible.

| Composante | Outil | Niveau | Preuve |
|:--|:--|:--|:--|
| IAM et MFA | Keycloak | N1 | TOTP, groupes, verrouillage |
| ZTNA sans agent | Pomerium | N1 | 403 malgré session valide |
| ZTNA par appareil | WireGuard | N2 | Clé par pair, sans posture |
| FWaaS | nftables | N2 | Refus journalisés, L3/L4 |
| SWG et DNS | Squid, dnsmasq | N1 / N2 | HTTP et DNS réels, HTTPS par nom |
| CASB | mitmproxy | N2 | Une application, règles par action |
| DLP | `dlp_engine.py` | N2 | Luhn, IBAN, NIR, EICAR |
| SD-WAN | WireGuard, nftables, agents | N2 | Deux liens, trois classes, bascule |
| Supervision | Fluent Bit, Loki, Grafana | N1 | Sept sources corrélées |
| Segmentation | Docker, nftables | N1 | Réseau apps isolé, FORWARD drop |
| PoP mondial, CASB API, TLS généralisé | — | N3 | Hors maquette |

: Tableau 4.12 — Bilan de réalisation par composante

### 4.9.2 Limites de la réalisation

- **Un seul PoP, une seule VM** : pas de redondance ni de latence géographique, et un domaine de panne commun.
- **ZTNA sans agent** : seuls les protocoles web sont couverts ; SSH, RDP et bases de données exigeraient un tunnel TCP ou une autre solution.
- **Posture d'appareil** réduite à l'identité cryptographique de l'appareil (clé WireGuard), sans contrôle d'antivirus, de chiffrement ni de mises à jour.
- **SWG** : HTTPS filtré par nom d'hôte seulement, et aucune authentification au proxy, donc pas de politique web par utilisateur.
- **CASB et DLP** : une application instrumentée, analyse textuelle du flux montant, assertion JWT non vérifiée en signature.
- **SD-WAN** : contrôleur remplacé par un fichier, mesures par ICMP, liens simulés par netem, pas d'hystérésis.
- **Laboratoire** : mots de passe de test, base Keycloak H2, certificat joker et clés privées en clair sur le disque.
- **Mesures** : valeurs relatives, représentatives d'un surcoût de chaîne et non d'un débit de production.

### 4.9.3 Perspectives d'amélioration

Pour dépasser ces limites sans dépasser 8 Go, une stratégie hybride combine la maquette locale — preuve de l'architecture et de l'intégration — et des services cloud d'essai utilisés comme comparaison, jamais présentés comme faisant partie du déploiement local :

- **offre Zero Trust gratuite d'un fournisseur cloud** : comparaison avec un ZTNA, un SWG et un DNS gérés mondialement ; les capacités CASB et DLP réellement incluses doivent être vérifiées au moment de l'essai ;
- **VM cloud d'essai** pour un contrôleur SD-WAN réel (flexiWAN) ou un SIEM (Wazuh), sans charger les 8 Go locaux ;
- **inspection TLS Squid** (`ssl_bump`) avec l'autorité du laboratoire, pour contrôler l'URL et les fichiers dans HTTPS, avec une réflexion sur la vie privée ;
- **authentification au proxy** et vérification de la signature JWT de bout en bout, pour une politique web par utilisateur et une chaîne de confiance complète ;
- **OpenZiti ou tunnel TCP Pomerium** pour un ZTNA non web (SSH, RDP) ;
- **Suricata en mode IDS** comme premier niveau de détection d'intrusion pour le FWaaS, au prix de 400 à 600 Mo, en arrêtant Grafana et Loki pendant le test.

### 4.9.4 Conclusion du chapitre

Ce chapitre a relaté la réalisation d'une maquette SASE en partant d'une situation de référence, le VPN suivi d'un pare-feu périmétrique, dont les limites — confiance implicite, backhaul, politiques dispersées, visibilité fragmentée, lien unique, absence de contrôle des applications cloud — ont été explicitées. La topologie cible a ensuite été construite étape par étape sur un portable de 8 Go : un tunnel qui n'ouvre que le PoP, un pare-feu en refus par défaut, une identité commune avec second facteur, une autorisation par application et par groupe, un contrôle des actions et des contenus, un filtrage web et DNS, un routage multi-chemins et une supervision unique.

Les scénarios observés confirment l'enchaînement des contrôles : l'accès authentifié de bout en bout, le refus Zero Trust malgré une session valide, le refus silencieux des flux interdits journalisé par le pare-feu, le filtrage web par domaine, URL et extension, et le blocage des données sensibles fictives. Les mesures de mémoire montrent que la faisabilité sur 8 Go est acquise, avec une marge d'environ 1 Go. Les mesures de latence et de reprise, ainsi que plusieurs preuves signalées dans le texte, restent à consigner pour vérifier les hypothèses quantitatives du chapitre 3. Les limites identifiées — PoP unique, inspection HTTPS partielle, ZTNA limité aux applications web, supervision sans corrélation SIEM — délimitent la portée des conclusions et dessinent les pistes d'évolution vers une architecture distribuée, plus résiliente et plus intégrée.

## Références normatives et cadres de conformité

Les référentiels suivants ont guidé les choix de conception, la politique de sécurité et la documentation du laboratoire. Ils ne valent pas certification : la maquette n'a pas fait l'objet d'un audit externe.

**Sécurité de l'information et services cloud**

- ISO/IEC 27001:2022 — *Information security, cybersecurity and privacy protection — Information security management systems — Requirements*.
- ISO/IEC 27002:2022 — *Information security, cybersecurity and privacy protection — Information security controls*.
- ISO/IEC 27017:2015 — *Code of practice for information security controls based on ISO/IEC 27002 for cloud services*.
- ISO/IEC 27018:2019 — *Code of practice for protection of personally identifiable information (PII) in public clouds acting as PII processors*.
- ISO/IEC 27019:2017 — *Information security controls for the energy utility industry* (pour la méthode de sélection des contrôles).
- ISO/IEC 27033-1:2015 — *Network security — Part 1: Overview and concepts*.

**Architecture de sécurité et Zero Trust**

- ITU-T Recommendation X.800 (1991) — *Security architecture for Open Systems Interconnection for CCITT applications*.
- ITU-T Recommendation X.805 (2003) — *Security architecture for systems providing end-to-end communications*.
- NIST SP 800-207 (2020) — *Zero Trust Architecture*.
- NIST SP 800-53 Rev. 5 (2020) — *Security and Privacy Controls for Information Systems and Organizations*.
- NIST SP 800-30 Rev. 1 (2012) — *Guide for Conducting Risk Assessments*.
- NIST SP 800-145 (2011) — *The NIST Definition of Cloud Computing*.
- ANSSI — *Guide d'hygiène informatique* (2017) et *Recommandations de sécurité relatives à TLS* (2020).

**Protocoles et interfaces**

- RFC 8446 (2018) — *The Transport Layer Security (TLS) Protocol Version 1.3*.
- RFC 6749 (2012) — *The OAuth 2.0 Authorization Framework*.
- RFC 7519 (2015) — *JSON Web Token (JWT)*.
- RFC 8414 (2018) — *OAuth 2.0 Authorization Server Metadata*.
- RFC 8484 (2018) — *DNS Queries over HTTPS (DoH)*.
- RFC 5280 (2008) — *Internet X.509 Public Key Infrastructure Certificate and CRL Profile*.
- OWASP — *Top 10* (2021) et *Application Security Verification Standard* (ASVS 4.0.3).

**Cadre national malgache**

- Loi n° 2014-006 du 17 juillet 2014 sur la lutte contre la cybercriminalité.
- Loi n° 2018-020 du 21 décembre 2018 sur la protection des données à caractère personnel.
- Ministère du Développement Numérique, de la Transformation Digitale, des Postes et des Télécommunications — orientations nationales en matière de cybersécurité.
- Autorité de Régulation des Technologies de l'Information et de la Communication (ARTEC) — textes relatifs aux réseaux et services de communications électroniques.

## Annexe 4.A — Arborescence du dépôt sase-lab

```text
sase-lab/
├── docker-compose.yml          # 5 réseaux, 15 services
├── .env                        # secrets générés par init.sh
├── config/sdwan-policy.env     # politique SD-WAN centrale
├── scripts/init.sh             # PKI, secrets, clés, rendu des modèles
├── pop-gw/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── sdwan-gw-agent.sh
│   ├── nftables.nft
│   └── wireguard/              # wg0.conf, wg-b1.conf, wg-b2.conf
├── dns/                        # dnsmasq.conf, blocklist.conf
├── squid/                      # squid.conf, blocked_domains.txt, blocked_urls.txt
├── pomerium/                   # config.yaml.tpl -> config.yaml
├── keycloak/                   # realm-sase.json.tpl -> realm-sase.json
├── casb/                       # casb_dlp.py, dlp_engine.py, policy.json
├── clouddrive/                 # app.py (Flask)
├── apps/                       # finance/, admin/ (pages statiques)
├── inet-sim/                   # nginx.conf, html/
├── branch/                     # edge-entrypoint.sh, sdwan-edge-agent.sh,
│                               # impair.sh, pc-entrypoint.sh, wireguard/
├── observability/              # loki-config.yml, fluent-bit.conf, datasource
├── tests/                      # make-sensitive-files.sh, mkjwt.sh
├── clients/                    # home-laptop.conf, mobile.conf, CA
├── certs/                      # PKI du laboratoire (non versionnée)
└── logs/                       # squid, dns, casb, sdwan
```

## Annexe 4.B — Table des preuves

| Réf. | Scénario ou étape | Contenu conservé |
|:--|:--|:--|
| E1 | Étape 0 | Gestionnaire de réseau VirtualBox : 192.168.56.1/24, DHCP désactivé |
| E2 | Étape 6 | `docker stats` et `free -m` après démarrage |
| E3 | S1 | Écran TOTP de Keycloak et page CloudDrive avec identité et groupes |
| E4 | S2 | Message d'erreur et verrouillage après cinq échecs |
| E5 | S2 | Absence de handshake pour un appareil non enregistré |
| E6 | S3 | Refus 403 de Pomerium pour carol sur Finance |
| E7 | S4 | Tests de ports (443 joignable, 22 et 8081 refusés) |
| E8 | S4 | Lignes `SASE-FW-INPUT-DROP` dans `kern.log` |
| E9 | S4 | Compteurs de la chaîne `forward` et refus `SASE-FW-FWD-DROP` |
| E10 | S5 | Codes HTTP et résolutions DNS à travers le SWG |
| E11 | S6 | Journal `events.jsonl` des décisions CASB |
| E12 | S7 | Page de blocage DLP et jeu de fichiers de test |
| E13 | S8 | Journal de l'agent SD-WAN et tables 101/102 |
| E14 | S9 | Tableau de bord Grafana et corrélation d'un incident |
