# PID Climate – Home Assistant Custom Integration

Custom **Climate** integrace pro Home Assistant umožňující řízení topení pomocí **P / PID regulace** s podporou **časového PWM**.  
Integrace je navržena především pro **binární akční členy** (relé, termopohony, KNX výstupy).

---

## ✨ Funkce

- Climate entita plně kompatibilní s Home Assistant UI
- Řízení výkonu na základě:
  - aktuální teploty
  - cílové teploty
- **P-regulátor** s plynulým náběhem výkonu
- **Časové PWM řízení**
  - ideální pro ON/OFF výstupy
- Podpora:
  - teplotního senzoru
  - volitelného senzoru vlhkosti (zobrazení v UI)
- Konfigurovatelné:
  - minimální / maximální teplota
  - teplotní krok
  - délka PWM periody
  - cílové teploty pro HVAC režimy
- Plně asynchronní, bez blokování

---

## 📦 Instalace

### Ruční instalace (custom component)

1. Zkopíruj adresář: custom_components/pid_climate do <config>/custom_components/

2. Restartuj Home Assistant

3. V UI přejdi na:
**Nastavení → Zařízení a služby → Přidat integraci → PID Climate**

---

## ⚙️ Konfigurace

Integrace používá **Config Flow** – není nutná žádná YAML konfigurace.

### Povinné položky

| Parametr | Popis |
|--------|-----|
| Název | Název termostatu |
| Entita teplotního senzoru | Zdroj aktuální teploty |
| Výstupní entita | `number` entita řízená PWM |

---

### Volitelné položky

| Parametr | Popis |
|--------|-----|
| Entita senzoru vlhkosti | Zobrazení vlhkosti v UI |
| Minimální teplota | Dolní mez regulace |
| Maximální teplota | Horní mez regulace |
| Teplotní krok | Krok nastavení cílové teploty |
| PWM perioda | Délka PWM periody (v minutách) |

---

### HVAC režimy

Každý HVAC režim má:
- vlastní výchozí cílovou teplotu
- možnost úpravy v **Options Flow**

Podporované režimy odpovídají KNX DPT 20.102:

- Auto
- Comfort
- Standby
- Economy
- Building protection

---

## 🔁 Jak funguje regulace

1. Z rozdílu: cílová teplota – aktuální teplota se vypočte **požadovaný výkon**

2. Výkon je:
- normalizován
- omezen na bezpečný rozsah

3. Výkon je aplikován pomocí **časového PWM**
- `0 %` → výstup trvale OFF
- `100 %` → výstup trvale ON
- jinak → ON/OFF dle PWM periody

---

## 💧 Vlhkost

- Pokud je nakonfigurován senzor vlhkosti:
- aktuální vlhkost se zobrazuje v UI termostatu
- Vlhkost:
- **neovlivňuje regulaci**
- slouží pouze jako informativní hodnota

---

## 🧠 Co integrace nedělá

- Neimplementuje:
- integrální / derivační složku PID (I / D)
- hysteresi
- adaptivní regulaci
- Neřídí:
- chlazení
- cílovou vlhkost

Tyto funkce mohou být doplněny v budoucnu.

---

## 🛠 Doporučené použití

Integrace je vhodná zejména pro:

- relé řízení topení
- termopohony (např. podlahové topení)
- KNX / Modbus / ESPHome výstupy
- systémy, kde není vhodná plynulá regulace výkonu

---

## 🧩 Kompatibilita

- Home Assistant Core (aktuální verze)
- Platforma: `climate`
- Výstup:
- `number` entita (`0–100 %` nebo `min/max`)

---

## 📄 Licence

MIT License

---

## 🚀 Možná budoucí rozšíření

- integrální složka PID (I)
- minimální ON / OFF čas (ochrana relé)
- statistiky PWM (runtime, duty cycle)
- využití vlhkosti v regulaci
- diagnostika a grafy

