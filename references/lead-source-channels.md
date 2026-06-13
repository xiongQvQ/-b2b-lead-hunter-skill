# Lead Source Channels

Beyond organic search, these discoverable sources yield high-quality, pre-filtered distributor leads.

## Distributor Network Pages (High Signal)

Major switch/component brands publish authorized distributor lists. These are gold because the companies listed are confirmed active in switch distribution.

| Brand | URL | Best For |
|---|---|---|
| Cherry | https://www.cherry.de/en-us/distributors-resellers | Germany, Austria, Eastern Europe |
| ITW Switches | https://www.itwswitches.com/distributors-emea | EMEA-wide (JS map, may need browser) |
| Honeywell | Search: "Honeywell authorized distributor {country}" | Per-country |
| Omron | https://components.omron.com/eu-en/about/corporate/global-network/eu/distributor | EU-wide |
| NorComp | https://www.norcomp.net/distributor/{country} | Per-country lists |
| EDAC | https://edac.net/distributor/{country} | Per-country lists |
| E-Switch | Search: "E-Switch distributor {country}" | Per-country |

**Mining technique**: Read the distributor page with Jina, then grep for company names, extract domains, and cross-reference each with a contact page read.

## Elevator / Lift Spare Parts (Vertical Niche)

Elevator components are a strong match for micro switch suppliers. These companies buy large volumes of door sensors, limit switches, safety switches.

Key players discovered:
- ISF Elevator Shop (Germany) — isfelevatorshop.de
- Hauer Spareparts / elevatorshop (Germany) — hauer-spareparts.com
- Lift-Spares (Sweden) — lift-spares.se

Search templates:
- `elevator lift spare parts wholesaler Europe micro switch`
- `lift component distributor Germany switch sensor`
- `Industrystock elevator components`

## Vending Machine Spare Parts (Vertical Niche)

Vending machines use multiple micro switches. Spare parts distributors for vending equipment are natural buyers.

Key players:
- REPA / REPA Italia — repagroup.com
- Sparetech (France) — sparetech.eu
- Applias (Czech) — applias.com

Search templates:
- `vending machine spare parts distributor Europe switch`
- `site:europages.co.uk vending machine parts`

## Country-Specific Leads

### Austria
Cherry resellers list revealed: Littlebit Technology (littlebit.at), e-tec electronic (e-tec.at)

### Italy
Honeywell authorized: Nicom Distribution (nicomdistribution.it)
Also: Ramos Srl (ramos.it)

### Portugal
Hermann Biener (hermannbiener.pt), JCCE (jcce.pt)

### Estonia / Baltic
Lemona (lemona.ee) — also serves Latvia and Lithuania
Teval Elektroonika (teval.ee)

### Hungary
Advanced MP Technology (advancedmp.com), local branch: zsoltg@advancedmp.com

### Greece
Qservice Electronics (qservice@otenet.gr)

### Romania
Romtek Electronics (romtek.ro)

### Croatia / Southeast Europe
Yotta Volt (yottavolt.com)

### Turkey
Özdisan (ozdisan.com), Ankaron (ankaron.com), Arkotek (arkotekelektronik.com), KMC Komponent (E-Switch distributor)

## Email Format Patterns (Discovered)

When inferring decision-maker emails from LinkedIn names, these domain patterns were confirmed:

| Domain | Pattern | Example |
|---|---|---|
| kempstoncontrols.co.uk | first.last | jenny.salmon@ |
| switchelectronics.co.uk | first | ben@ |
| alders.de | first.last | martin.alders@ |
| anglia.com | first.last | debbie.marriott@ |
| tme.pl | first.last | jagoda.zak-ling@ |
| ropla.eu | first_initial.last | p.hryckiewicz@ |
| wittig-electronic.de | first.last | michael.wittig@ |
| neumueller.com | first.last | silvia.kirchhoff@ |
| emc.de | first.last | fabian.girolstein@ |
| scanditron.se | first.last | bjorn.johnsson@ |
| yottavolt.com | first_initial.last | b.jokanovic@ |
| littlebit-group.com | first.last | franz.burghardt@ |
| nicom.it | first_initial.last | g.deluca@ |
| heilind.eu | flast | psullivan@ |
| e-tec.at | first.last | marco.krankl@ |
| perel.fi | first.last | jari.rantala@ |
