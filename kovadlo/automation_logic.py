"""
Логіка керування (модуль 13): сценарій як набір правил "умова -> дія",
стани системи, таймери/затримки, блокування неможливих переходів.

Механізм навмисно декларативний (умова й дія — дані, не довільний
Python-код): це дозволяє статично перевірити сценарій (глухі кути,
заборонені переходи — `find_dead_end_states`, `find_forbidden_rule_violations`)
і легко покласти в текстовий звіт.

Вхідні й вихідні сигнали в цьому русі — булеві (спрацював/ні, увімкнено/
вимкнено): для дискретної автоматики (кінцевики, кнопки, реле, фото-
бар'єри) цього достатньо; аналогові порогові умови (напр. "температура
> 30°C") у цій версії не підтримуються — їх треба заздалегідь звести до
булевого сигналу (наприклад, самим датчиком чи окремим порівнянням поза
цим модулем).

Правила перевіряються по черзі (порядок списку — це і є пріоритет):
спрацьовує ПЕРШЕ правило, чия умова виконується. Це, зокрема, дає
природний спосіб реалізувати аварійний стоп — правило з умовою на
аварійний вхід, поставлене першим у списку, перекриває всі інші.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Condition:
    """Умова спрацювання правила.

    `state_in=None` означає "у будь-якому стані". `inputs` — вимоги до
    значень конкретних сигналів (усі мають збігатися). `timer_expired`
    — ім'я таймера, який має бути вже сплив."""

    state_in: str | None = None
    inputs: dict[str, bool] = field(default_factory=dict)
    timer_expired: str | None = None

    def matches(self, state: str, input_values: dict[str, bool], expired_timers: set[str]) -> bool:
        if self.state_in is not None and state != self.state_in:
            return False
        if self.timer_expired is not None and self.timer_expired not in expired_timers:
            return False
        return all(input_values.get(name) == value for name, value in self.inputs.items())


@dataclass(frozen=True)
class Action:
    """Дія правила: новий стан (якщо задано), значення виходів для
    встановлення, запуск/зупинка таймера."""

    new_state: str | None = None
    outputs: dict[str, bool] = field(default_factory=dict)
    start_timer: str | None = None
    stop_timer: str | None = None


@dataclass(frozen=True)
class Rule:
    """Одне правило "умова -> дія"."""

    name: str
    condition: Condition
    action: Action


@dataclass(frozen=True)
class TimerSpec:
    """Опис таймера: ім'я + тривалість, с."""

    name: str
    duration_s: float

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise ValueError("Тривалість таймера має бути додатною")


@dataclass(kw_only=True)
class Scenario:
    """Повний сценарій автоматики: стани, правила, таймери, заборонені
    переходи, дозволені кінцеві стани (не вважаються глухим кутом)."""

    name: str
    states: set[str]
    initial_state: str
    rules: list[Rule] = field(default_factory=list)
    timers: dict[str, TimerSpec] = field(default_factory=dict)
    forbidden_transitions: set[tuple[str, str]] = field(default_factory=set)
    terminal_states: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.initial_state not in self.states:
            raise ValueError(f"Початковий стан «{self.initial_state}» не входить у states")
        if not self.terminal_states <= self.states:
            raise ValueError("terminal_states має бути підмножиною states")
        for frm, to in self.forbidden_transitions:
            if frm not in self.states or to not in self.states:
                raise ValueError(f"Заборонений перехід ({frm!r} -> {to!r}) посилається на невідомий стан")
        for rule in self.rules:
            if rule.condition.state_in is not None and rule.condition.state_in not in self.states:
                raise ValueError(f"Правило «{rule.name}»: невідомий стан умови «{rule.condition.state_in}»")
            if rule.action.new_state is not None and rule.action.new_state not in self.states:
                raise ValueError(f"Правило «{rule.name}»: невідомий цільовий стан «{rule.action.new_state}»")
            for timer_name in (rule.condition.timer_expired, rule.action.start_timer, rule.action.stop_timer):
                if timer_name is not None and timer_name not in self.timers:
                    raise ValueError(f"Правило «{rule.name}»: невідомий таймер «{timer_name}»")


@dataclass
class MachineState:
    """Поточний стан автомата в процесі виконання: стан системи,
    значення входів/виходів, момент запуску активних таймерів."""

    state: str
    input_values: dict[str, bool] = field(default_factory=dict)
    output_values: dict[str, bool] = field(default_factory=dict)
    timer_started_at: dict[str, float] = field(default_factory=dict)


def expired_timers(scenario: Scenario, machine_state: MachineState, current_time_s: float) -> set[str]:
    """Імена активних таймерів, чия тривалість уже минула на момент
    `current_time_s`."""
    result = set()
    for name, started_at in machine_state.timer_started_at.items():
        spec = scenario.timers[name]
        if current_time_s - started_at >= spec.duration_s:
            result.add(name)
    return result


def _apply_rule(scenario: Scenario, machine_state: MachineState, rule: Rule, current_time_s: float) -> None:
    action = rule.action
    if action.new_state is not None and action.new_state != machine_state.state:
        if (machine_state.state, action.new_state) in scenario.forbidden_transitions:
            raise RuntimeError(
                f"Заблокований перехід «{machine_state.state}» -> «{action.new_state}» (правило «{rule.name}»)"
            )
        machine_state.state = action.new_state
    machine_state.output_values.update(action.outputs)
    if action.start_timer is not None:
        machine_state.timer_started_at[action.start_timer] = current_time_s
    if action.stop_timer is not None:
        machine_state.timer_started_at.pop(action.stop_timer, None)


def apply_step(scenario: Scenario, machine_state: MachineState, current_time_s: float) -> list[Rule]:
    """Застосовує всі правила, що спрацьовують у момент `current_time_s`,
    одне за одним (перше за списком, що збігається, щоразу) — це дає
    каскад (одна дія міняє стан/виходи, від чого одразу спрацьовує
    наступне правило). Повертає список правил, що спрацювали, у
    порядку спрацювання.

    Кожне правило може спрацювати НЕ БІЛЬШЕ ОДНОГО РАЗУ за один виклик
    (за іменем) — і цього досить, і це гарантує завершення без
    штучного ліміту ітерацій: якщо однакова умова (напр. правило без
    прив'язки до стану, типу аварійного стопу) продовжує виконуватися,
    повторне спрацювання того самого правила на тому самому кроці
    нічого нового не додало б (та сама дія з тими самими даними), тож
    воно просто пропускається на наступних ітераціях цього кроку.
    """
    fired: list[Rule] = []
    fired_names: set[str] = set()
    while True:
        expired = expired_timers(scenario, machine_state, current_time_s)
        matched = next(
            (
                r
                for r in scenario.rules
                if r.name not in fired_names and r.condition.matches(machine_state.state, machine_state.input_values, expired)
            ),
            None,
        )
        if matched is None:
            return fired
        _apply_rule(scenario, machine_state, matched, current_time_s)
        fired.append(matched)
        fired_names.add(matched.name)


def find_dead_end_states(scenario: Scenario) -> set[str]:
    """Стани, з яких немає жодного правила, що вело б в ІНШИЙ стан
    (глухий кут) — крім явно дозволених `terminal_states`."""
    states_with_exit: set[str] = set()
    for rule in scenario.rules:
        if rule.action.new_state is None:
            continue
        sources = {rule.condition.state_in} if rule.condition.state_in is not None else set(scenario.states)
        for src in sources:
            if rule.action.new_state != src:
                states_with_exit.add(src)
    return scenario.states - states_with_exit - scenario.terminal_states


def find_forbidden_rule_violations(scenario: Scenario) -> list[Rule]:
    """Статична перевірка: правила, чий перехід (стан умови -> цільовий
    стан) входить у `forbidden_transitions` — тобто сценарій ЗАВЖДИ
    порушить блокування, якщо таке правило колись спрацює (на відміну
    від `apply_step`, яке ловить це лише в момент реального спрацювання)."""
    violations = []
    for rule in scenario.rules:
        if rule.action.new_state is None:
            continue
        sources = {rule.condition.state_in} if rule.condition.state_in is not None else set(scenario.states)
        if any((src, rule.action.new_state) in scenario.forbidden_transitions for src in sources):
            violations.append(rule)
    return violations
