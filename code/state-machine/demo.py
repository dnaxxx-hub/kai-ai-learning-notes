"""演示 — 交通灯 FSM & 电梯 HSM"""

from fsm import FSM, State
from machine import StateMachine
from hsm import HSM, HSMachine


# 交通灯 FSM
def traffic_light_demo():
    green = State('green', on_enter=lambda ctx: print("🟢 绿灯亮"))
    yellow = State('yellow', on_enter=lambda ctx: print("🟡 黄灯亮"))
    red = State('red', on_enter=lambda ctx: print("🔴 红灯亮"))

    fsm = FSM('traffic_light')
    fsm.add_state(green, initial=True)
    fsm.add_state(yellow)
    fsm.add_state(red)

    fsm.add_transition('green', 'timer', 'yellow',
                       action=lambda ctx: print("→ 准备变黄"))
    fsm.add_transition('yellow', 'timer', 'red',
                       action=lambda ctx: print("→ 准备变红"))
    fsm.add_transition('red', 'timer', 'green',
                       action=lambda ctx: print("→ 准备变绿"))

    machine = StateMachine(fsm)

    for _ in range(6):
        machine.send('timer')


# 电梯 HSM
def elevator_demo():
    hsm = HSM('elevator')

    idle = hsm.add_state('idle', initial=True,
                         on_enter=lambda ctx: print("🚪 电梯待机"))
    moving = hsm.add_state('moving',
                           on_enter=lambda ctx: print("🛗 电梯运行中"))
    idle_on_floor = hsm.add_state(
        'idle_on_floor', parent='idle',
        on_enter=lambda ctx: print(f"  📍 停靠在{ctx.get('floor', '?')}楼"))

    hsm.add_transition('idle', 'call', 'moving')
    hsm.add_transition('moving', 'arrive', 'idle_on_floor')
    hsm.add_transition('idle_on_floor', 'call', 'moving')

    sm = HSMachine(hsm)
    print(f"当前: {sm.active_states}")
    sm.hsm.context['floor'] = 1
    sm.send('call')
    sm.send('arrive')
    sm.hsm.context['floor'] = 5
    sm.send('call')
    sm.send('arrive')


if __name__ == '__main__':
    traffic_light_demo()
    print()
    elevator_demo()
