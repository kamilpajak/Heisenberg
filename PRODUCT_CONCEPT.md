# Product Concept: The Heisenberg

## 1. Executive Summary

**The Heisenberg** to agent AI typu SaaS, który automatycznie diagnozuje przyczyny niestabilnych testów (flaky tests) w środowiskach CI/CD.

| Element | Opis |
|---------|------|
| **Problem** | Inżynierowie tracą 10-20% czasu na debugowanie testów, które "raz działają, raz nie" |
| **Rozwiązanie** | Automatyczna korelacja trace'ów z testów E2E z logami backendowymi i metrykami infrastruktury |
| **Rynek docelowy** | Średnie i duże zespoły deweloperskie z architekturą mikroserwisową |
| **Model biznesowy** | B2B SaaS, pricing per-seat ($29/user/mies.) |

---

## 2. Problem i okazja rynkowa

### Opis problemu

W nowoczesnych zespołach deweloperskich (szczególnie w architekturze mikroserwisów):

- **Koszt czasowy:** Inżynierowie tracą 10-20% czasu na debugowanie niestabilnych testów
- **Utrata zaufania:** Zespoły ignorują czerwone testy ("to tylko ten flaky test, puść deploy"), co prowadzi do błędów na produkcji
- **Silosy danych:** Narzędzia frontendowe (Playwright Trace Viewer) nie widzą problemów backendowych (GC pause, locki w bazie)

### Obecne rozwiązania i ich ograniczenia

| Rozwiązanie | Ograniczenie |
|-------------|--------------|
| Ręczna analiza (grep, Kibana) | Czasochłonne, wymaga ekspertyzy |
| Datadog / New Relic | Drogie, skomplikowane, nie zoptymalizowane pod CI/CD |
| BuildPulse / Retry | Zarządzają problemem, nie diagnozują przyczyny |
| Playwright Trace Viewer | Ślepe na backend i infrastrukturę |

### Dlaczego teraz?

- Rosnąca popularność Playwright i testów E2E w CI/CD
- Powszechność mikroserwisów zwiększa złożoność debugowania
- Dojrzałość LLM umożliwia inteligentną analizę logów
- Zespoły coraz bardziej świadome kosztów "flaky tests"

---

## 3. Grupa docelowa

### Ideal Customer Profile (ICP)

| Atrybut | Wartość |
|---------|---------|
| **Wielkość firmy** | 20-500 deweloperów |
| **Architektura** | Mikroserwisy, konteneryzacja (Docker/K8s) |
| **Stack testowy** | Playwright lub Cypress dla E2E |
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins |
| **Infrastruktura logów** | ELK, Loki, CloudWatch lub podobne |
| **Ból** | >100 testów E2E, regularne problemy z niestabilnością |

### Buyer Persona: Engineering Manager / VP of Engineering

- **Cele:** Skrócenie cyklu developmentu, redukcja kosztów CI/CD, poprawa morale zespołu
- **Frustracje:** Zespół traci czas na debugowanie zamiast budować features, trudno zmierzyć ROI testów
- **Metryki sukcesu:** Czas od PR do deploy, % testów przechodzących na pierwszą próbę

### User Persona: Senior Developer / QA Engineer

- **Zadania:** Debugowanie padających testów, utrzymanie pipeline'u CI/CD
- **Frustracje:** Musi ręcznie korelować dane z wielu źródeł, brak kontekstu backendowego w trace'ach
- **Umiejętności:** Zna Playwright, podstawowa znajomość infrastruktury, nie jest ekspertem od observability

---

## 4. Propozycja wartości

> **Pomagamy zespołom deweloperskim skrócić czas debugowania flaky testów z godzin do minut poprzez automatyczną korelację trace'ów E2E z logami backendowymi i dostarczenie diagnozy w komentarzu do PR.**

### Kluczowe benefity

| Feature | Benefit | Outcome |
|---------|---------|---------|
| Temporal Correlation Engine | Automatycznie łączy timestamp testu z logami backendu | Deweloper nie musi ręcznie szukać w Kibanie |
| Infrastructure Awareness | Wykrywa problemy CPU, pamięci, GC w czasie awarii | Diagnoza wykracza poza kod testu |
| Pattern Recognition | Uczy się wzorców (np. błąd X = backup bazy) | Mniej fałszywych alarmów z czasem |
| PR Comment Bot | Diagnoza pojawia się automatycznie w PR | Zero przełączania kontekstu |
| Confidence Score | Pokazuje pewność diagnozy | Deweloper wie, czy warto podążać za sugestią |

---

## 5. Zakres produktu

### Wizja (2-3 lata)

Heisenberg staje się standardowym narzędziem w każdym pipeline CI/CD, automatycznie diagnozując nie tylko flaky testy, ale wszystkie anomalie w procesie developmentu.

### MVP Scope (Faza 1)

| W zakresie | Poza zakresem |
|------------|---------------|
| Integracja z Playwright (JSON reports + traces) | Cypress, Selenium (później) |
| GitHub Actions jako CI | GitLab CI, Jenkins (później) |
| Logi z stdout/stderr kontenerów Docker | Zaawansowane APM (Datadog traces) |
| Komentarz w PR z diagnozą | Dashboard webowy |
| Analiza przez Claude/GPT API | Model on-premise |
| Angielski interfejs | Wielojęzyczność |

### User Stories (MVP)

1. **Jako deweloper**, gdy mój test E2E padnie w CI, chcę **automatycznie otrzymać diagnozę w komentarzu do PR**, abym nie musiał ręcznie przeszukiwać logów.

2. **Jako deweloper**, chcę **widzieć logi backendowe z okna czasowego +/- 30s od awarii**, abym mógł zrozumieć kontekst infrastrukturalny.

3. **Jako deweloper**, chcę **widzieć confidence score diagnozy**, abym wiedział, czy warto podążać za sugestią AI.

4. **Jako Engineering Manager**, chcę **widzieć historię diagnoz**, abym mógł identyfikować powtarzające się wzorce problemów.

---

## 6. Architektura techniczna (MVP)

### Stack

| Warstwa | Technologia |
|---------|-------------|
| **Input** | Playwright JSON reports + trace.zip, logi Docker (stdout/stderr) |
| **Backend** | Python (FastAPI) |
| **Baza danych** | PostgreSQL + pgvector (do podobnych awarii) |
| **AI** | Claude 3.5 Sonnet / GPT-4o via API |
| **Integracja** | GitHub Actions, GitHub API (komentarze PR) |
| **Hosting** | Cloud (AWS/GCP), multi-tenant |

### Workflow

```
1. CI Pipeline → Test Failed
2. GitHub Action "heisenberg-analyze" uruchamia się
3. Pobiera: trace.zip, logi kontenerów, metryki (opcjonalnie)
4. Wysyła do Heisenberg API
5. AI analizuje korelacje czasowe
6. Bot postuje komentarz w PR z diagnozą
```

### Wyzwania techniczne

| Wyzwanie | Rozwiązanie |
|----------|-------------|
| **Clock Skew** | Normalizacja timestampów względem jednego źródła |
| **Szum w logach** | Wstępne filtrowanie przez mniejszy model (Haiku) |
| **Koszt LLM** | Agresywna kompresja kontekstu, cache podobnych awarii |
| **Onboarding** | Gotowe integracje dla popularnych stacków, "zero-config" setup |

---

## 7. Model biznesowy

### Pricing

| Plan | Cena | Target | Zawartość |
|------|------|--------|-----------|
| **Open Source** | $0 | Indie devs, małe zespoły | GitHub Action z podstawową analizą (tylko tekst błędu) |
| **Team** | $29/user/mies. | Software House, startupy | Pełna korelacja z logami, historia 30 dni, Slack integration |
| **Enterprise** | Custom ($1k+/mies.) | Korporacje | On-premise, SSO, SLA, dedykowany support |

### Unit Economics (założenia)

| Metryka | Cel |
|---------|-----|
| CAC (koszt pozyskania klienta) | < $500 |
| LTV (wartość życiowa klienta) | > $2,500 |
| Payback period | < 6 miesięcy |
| Gross margin | > 70% (po optymalizacji kosztów LLM) |

---

## 8. Strategia Go-to-Market

### Faza 1: Open Source Core (miesiące 1-3)

- Wypuścić darmową GitHub Action z podstawową analizą
- Budować community na GitHubie, Discord
- Content marketing: blog posts, case studies
- Cel: 1,000 instalacji, 100 aktywnych użytkowników

### Faza 2: SaaS MVP (miesiące 4-8)

- Dashboard webowy z historią i trendami
- Integracja logów backendowych
- Wprowadzenie płatności (plan Team)
- Cel: 20 płacących klientów, $5k MRR

### Faza 3: Scale (miesiące 9-18)

- Integracje: GitLab CI, Jenkins, Cypress
- Wsparcie dla więcej języków (Java, Node.js, C#)
- Enterprise features (SSO, on-premise)
- Cel: 100 klientów, $50k MRR

---

## 9. Analiza konkurencji

### Mapa konkurencyjna

| Konkurent | Typ | Mocne strony | Słabe strony | Nasza przewaga |
|-----------|-----|--------------|--------------|----------------|
| **Datadog** | Observability platform | Kompletne dane, brand | Drogi, skomplikowany, nie dla CI/CD | Prostota, focus na flaky tests |
| **BuildPulse** | Test management | Automatyczna kwarantanna | Nie diagnozuje przyczyn | Root cause analysis |
| **Playwright Trace Viewer** | Debug tool | Darmowy, szczegółowy | Manualny, ślepi na backend | Automatyzacja + korelacja |
| **In-house scripts** | DIY | Darmowy, dopasowany | Wymaga utrzymania | Gotowy produkt, AI |

### Pozycjonowanie

**"The best companion for Playwright"** - skupienie na jednej, dobrze rozwiązanej integracji zamiast bycia "kolejną platformą observability".

---

## 10. Mierniki sukcesu

### Metryki biznesowe (lagging)

| Metryka | Cel 6 mies. | Cel 12 mies. |
|---------|-------------|--------------|
| MRR | $5,000 | $30,000 |
| Płacący klienci | 20 | 80 |
| Churn rate | < 5%/mies. | < 3%/mies. |

### Metryki produktowe (leading)

| Metryka | Cel |
|---------|-----|
| Czas do pierwszej diagnozy (onboarding) | < 15 minut |
| % diagnoz oznaczonych jako "pomocne" | > 60% |
| Tygodniowa retencja aktywnych użytkowników | > 70% |
| NPS | > 40 |

---

## 11. Ryzyka i założenia

### Kluczowe ryzyka

| Ryzyko | Prawdopodobieństwo | Impact | Mitigacja |
|--------|-------------------|--------|-----------|
| Trudny onboarding (różne formaty logów) | Wysokie | Wysoki | Gotowe integracje, "zero-config" dla popularnych stacków |
| Halucynacje AI (błędne diagnozy) | Średnie | Wysoki | Confidence score, walidacja na zbiorze testowym |
| Wysokie koszty LLM | Średnie | Średni | Mniejsze modele do filtracji, cache, optymalizacja promptów |
| Obawy o prywatność (wysyłanie logów) | Średnie | Średni | Anonimizacja, opcja on-premise dla Enterprise |
| Kopiowanie przez dużych graczy | Niskie | Wysoki | Szybka iteracja, budowanie community, focus na UX |

### Kluczowe założenia do zwalidowania

1. **Zespoły są gotowe wysyłać logi do zewnętrznego serwisu** - wymaga rozmów z potencjalnymi klientami
2. **AI jest w stanie poprawnie diagnozować >50% przypadków** - wymaga prototypu i testów
3. **Problem jest wystarczająco bolesny, żeby za niego płacić** - wymaga walidacji cenowej
4. **Onboarding można zrobić w <15 minut** - wymaga technicznego spike'a

---

## 12. Następne kroki

1. [ ] Zbudować prototyp GitHub Action z podstawową analizą
2. [ ] Przeprowadzić 10 wywiadów z potencjalnymi klientami (ICP)
3. [ ] Przetestować dokładność AI na 50 realnych przypadkach flaky testów
4. [ ] Zwalidować gotowość do płacenia (pricing survey)
5. [ ] Opublikować MVP open source i zebrać feedback
