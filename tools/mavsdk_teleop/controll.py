import asyncio
from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.manual_control import ManualControlError
import KeyPressModule as kp

kp.init()
drone = System()

roll, pitch, throttle, yaw = 0.0, 0.0, 0.5, 0.0
armed = False
in_air = False
manual_started = False


async def track_state(my_drone):
    async def watch_armed():
        global armed
        async for a in my_drone.telemetry.armed():
            armed = a

    async def watch_in_air():
        global in_air
        async for a in my_drone.telemetry.in_air():
            in_air = a

    await asyncio.gather(watch_armed(), watch_in_air())


async def print_flight_mode(my_drone):
    async for fm in my_drone.telemetry.flight_mode():
        print("FlightMode:", fm)
        break  # print once, don't leave a stream running


async def getKeyboardInput(my_drone):
    global roll, pitch, throttle, yaw
    value = 0.5
    prev = {"r": False, "l": False, "i": False}

    while True:
        roll, pitch, throttle, yaw = 0.0, 0.0, 0.5, 0.0

        if kp.getKey("LEFT"):
            pitch = -value
        elif kp.getKey("RIGHT"):
            pitch = value
        if kp.getKey("UP"):
            roll = value
        elif kp.getKey("DOWN"):
            roll = -value
        if kp.getKey("w"):
            throttle = 1.0
        elif kp.getKey("s"):
            throttle = 0.0
        if kp.getKey("a"):
            yaw = -value
        elif kp.getKey("d"):
            yaw = value

        # one-shot actions: trigger only on the key-down edge
        now = {k: kp.getKey(k) for k in prev}
        try:
            if now["r"] and not prev["r"]:
                if armed:
                    print("Already armed")
                else:
                    await my_drone.action.arm()
                    print("-- Armed")
            if now["l"] and not prev["l"]:
                if in_air:
                    await my_drone.action.land()
                    print("-- Landing")
                else:
                    print("Not in air")
            if now["i"] and not prev["i"]:
                asyncio.ensure_future(print_flight_mode(my_drone))
        except ActionError as e:
            print("Action failed:", e)  # loop keeps running
        prev = now

        await asyncio.sleep(0.05)


async def manual_control_drone(my_drone):
    global manual_started
    while True:
        try:
            await my_drone.manual_control.set_manual_control_input(
                roll, pitch, throttle, yaw
            )
            if armed and not manual_started:
                await my_drone.manual_control.start_position_control()
                manual_started = True
                print("-- Position control started")
            elif not armed:
                manual_started = False
        except ManualControlError as e:
            print("Manual control error:", e)
        await asyncio.sleep(0.05)


async def main():
    await drone.connect(system_address="udp://0.0.0.0:14540")
    print("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("-- Connected to drone!")
            break

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("-- Global position state is good enough for flying.")
            break

    # gather() surfaces exceptions instead of swallowing them
    await asyncio.gather(
        track_state(drone),
        getKeyboardInput(drone),
        manual_control_drone(drone),
    )


if __name__ == "__main__":
    asyncio.run(main())
