import serial as serial_
import time, logging
import warnings
# TODO: ask ivory
# from ti_control.device_connection import SerialDeviceConnection

from serial.serialutil import SerialException
# from ti_control.device_connection import SerialDeviceConnection

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class EuropaControl:
    # 70000 + a few steps in VTP2 tube
    max_steps = 40000

    def __init__(self, steps_per_volume_ul, port, baud=115200, bytesize=8, timeout=2):
        self.logger = logger.getChild(self.__class__.__name__)
        self.somatic = serial_.Serial(port=port, baudrate=baud, bytesize=bytesize,
                                      timeout=timeout, stopbits=serial_.STOPBITS_ONE)

        self.acceleration = 3000
        self.max_speed = 1500  # in steps/s
        self.position = 0
        self._steps_per_volume_ul = steps_per_volume_ul
        self.logger.info(f"established connection with {self.somatic} at {port}")

        self.set_acceleration(self.acceleration)
        self.pump_set_max_speed(self.max_speed)

    def connect(self):
        # todo does this actually ever get called? doesnt seem like it
        self.somatic.__init__()

        self.set_acceleration(self.acceleration)
        self.pump_set_max_speed(self.max_speed)

    def disconnect(self):
        # put capper in its default state of "closed" before closing connection
        self.home_syringe()  # todo should we actually be homing here?
        self.somatic.close()
        self.logger.info("disconnected sampler")

    def pump_set_max_speed(self, speed, wait=True):
        # speed is given in steps/s
        cmd = f"SCRS {speed}"
        self.max_speed = speed
        self.logger.info(f"set max speed to {speed}.")
        self._execute(cmd, wait=wait)

    def switch_valve(self, pos: int, wait=True):
        self.logger.info(f"switching valve to {pos}.")
        cmd = f"VTP{pos}"
        self._execute(cmd, wait=wait)

    def move_syringe_to_position(self, position: int, wait=True):
        """
        Move the syringe stepper motor to the absolute position in terms of steps
        :param position: step count
        :param wait:
        :return:
        """
        steps = position - self.position
        steps *= -1
        cmd = f'SPSS {steps}'
        self.logger.info(f'Moving syringe to position {position}')
        self._execute(cmd, wait=wait)
        self.position = position

    def dispense_ul(self, vol_ul: float, extra_wait_s=0, timeout_s=600, wait=True):
        steps = self.steps_per_volume_ul * vol_ul
        cmd = f"SPSS {steps}"
        self.logger.info(f"dispense {vol_ul} ul")
        self._execute(cmd, timeout_s=timeout_s, wait=wait)
        self.position += steps
        time.sleep(extra_wait_s)

    def aspirate_ul(self, vol_ul: float, extra_wait_s=0, timeout_s=600, wait=True):
        steps = self.steps_per_volume_ul * vol_ul * -1
        cmd = f"SPSS {steps}"
        self.logger.info(f"aspirating {vol_ul} ul.")
        self._execute(cmd, timeout_s=timeout_s, wait=wait)
        self.position += steps
        time.sleep(extra_wait_s)

    def set_acceleration(self, acl):
        self.acceleration = acl
        cmd = f"SIRS {acl}"
        self._execute(cmd)

    def set_max_homing_speed(self, speed):
        cmd = f"SHRS {speed}"
        self._execute(cmd)

    def set_homing_direction(self, dir):
        cmd = f"SHDS {dir}"
        self._execute(cmd)

    def stop_motor(self):
        cmd = "STPS"
        self._execute(cmd)

    def home_syringe(self):
        cmd = "HMES"
        self._execute(cmd)
        self.position = 0

    def home_valve(self):
        cmd = 'HMEV'
        self._execute(cmd)

    def _turn_off(self):
        warnings.warn(
            'the method _turn_off() is deprecated and is no longer necessary. Please do not use it.',
            DeprecationWarning,
            stacklevel=2,
        )
        cmd = "RLY"
        self._execute(cmd)

    # def get_steps_to_go(self):
    #     cmd = "QCPS"
    #     steps = self._execute(cmd)
    #     return steps

    # def get_target_pos(self):
    #     cmd = "QTPS"
    #     target_pos = self._execute(cmd)
    #     return target_pos

    # def get_max_speed(self):
    #     cmd = "QCRS"
    #     max_speed = self._execute(cmd)
    #     return max_speed

    # def get_acceleration(self):
    #     cmd = "QIRS"
    #     acl = self._execute(cmd)
    #     return acl

    # def get_airgap(self, airgap_ul):
    #     self.pump_set_max_speed(1200)
    #     self.aspirate_ul(airgap_ul, wait=True)
    #     self.pump_set_max_speed(500)

    def get_is_running(self):
        cmd = "BSYS"
        is_running = self._execute(cmd)
        return is_running

    def _execute(self, cmd, timeout_s=180, wait=True, retries=3):
        try:
            self.logger.info(f"executing {cmd}")
            self.somatic.reset_input_buffer()
            self.somatic.reset_output_buffer()
            self.somatic.write(cmd.encode())

            if not wait:
                return

            ans = "-3"
            ans2 = "-3"
            ans3 = "-3"
            ans4 = "-3"
            start_time = time.time()

            while "-4" not in [ans, ans2, ans3, ans4]:
                self.somatic.write("BSY".encode())
                time.sleep(0.1)
                ans = self.somatic.readline().decode("unicode_escape").strip()
                ans2 = self.somatic.readline().decode("unicode_escape").strip()
                ans3 = self.somatic.readline().decode("unicode_escape").strip()
                ans4 = self.somatic.readline().decode("unicode_escape").strip()
                # self.logger.info("_____________")
                # self.logger.info(f"{ans=!a}")
                # self.logger.info("")
                # self.logger.info(f"{ans2=!a}")
                # self.logger.info("")
                # self.logger.info(f"{ans3=!a}")
                # self.logger.info("")
                # self.logger.info(f"{ans4=!a}")

                # if "-2" in [ans, ans2, ans3, ans4]:
                #     self.logger.info(f"{cmd} is an invalid command. Nothing will happen")
                #     break

                if int(time.time() - start_time) > timeout_s:
                    raise Exception(f"Timeout Error: SALSA action took longer than {timeout_s}.")
        except SerialException as e:
            if retries <= 0:
                raise e
            self.logger.warning(f'Retrying execute command, {retries} retries remaining')
            self.somatic.close()
            self.somatic.open()
            return self._execute(cmd, timeout_s=timeout_s, wait=wait, retries=retries - 1)

    @property
    def steps_per_volume_ul(self) -> float:
        return self._steps_per_volume_ul

    @steps_per_volume_ul.setter
    def steps_per_volume_ul(self, value: float):
        self._steps_per_volume_ul = value

    @property
    def syringe_volume_ul(self) -> float:
        return self.max_steps / self._steps_per_volume_ul


class EuropaControlV2:
    def __init__(self, port: str, baud: int = 115200):
        self.logger = logger.getChild(self.__class__.__name__)

        self.somatic = None
        # SerialDeviceConnection(serial_port=port, baudrate=baud, read_timeout=5)

        self.connection_info = {'module': {'address': 1, 'device_id': 0},
                                'syringe': {'address': 1, 'device_id': 1},
                                'needle': {'address': 1, 'device_id': 2},
                                'valve': {'address': 1, 'device_id': 3},
                                'bubble_sensor': {'address': 1, 'device_id': 4}}

        self.max_steps = 40000  # todo should be an init argument?
        self.syringe_volume_ul = 1000  # based off syringe datasheet  # todo should be an init argument?

        self.needle_port = 0
        self.backing_solvent_port = 1
        self.syringe_acceleration = 500    # steps/s/s
        self.needle_acceleration = 500  # steps/s/s
        self.syringe_max_speed = 0  # in steps/s
        self.needle_max_speed = 0  # in steps/s
        self.syringe_position = 0   # steps
        self.needle_position = 0    # needle
        self.max_syringe_travel = 30    # mm
        self.max_needle_travel = 120    # mm
        self.lead_screw_pitch = 2   # mm/rev
        self.syringe_microstep = 8
        self.needle_microstep = 8
        self.stepper_motor_resolution = 200     # step/rev
        self.max_syringe_steps = self.stepper_motor_resolution * self.syringe_microstep * self.max_syringe_travel / self.lead_screw_pitch    # steps
        #self.max_needle_steps = self.stepper_motor_resolution * self.needle_microstep * self.max_needle_travel / self.lead_screw_pitch
        self.max_needle_steps = 72000 #steps
        self._steps_per_volume_actual = 50
        # self._steps_per_volume = self.stepper_motor_resolution * self.syringe_microstep * self.max_syringe_travel / (self.syringe_volume_ul * self.lead_screw_pitch)    # step/uL
        self._steps_per_volume = 24.35 # todo remove this, set via database params
        self._steps_per_mm = self.stepper_motor_resolution * self.syringe_microstep / self.lead_screw_pitch    # step/mm
        self.profile_slope = 1
        self.profile_intercept = 0
        self.logger.info(f"established connection with {self.somatic} at {port}")

        self.syringe_max_speed = self.get_syringe_speed()

        self.needle_max_speed = self.get_needle_speed()

        # self.syringe_home()
        # self.needle_home()

    def connect(self):
        # todo does this actually ever get called? doesnt seem like it
        self.somatic.__init__()

        self.syringe_set_acceleration(self.syringe_acceleration)
        self.syringe_set_max_speed(self.syringe_max_speed)

        self.needle_set_acceleration(self.needle_acceleration)
        self.needle_set_max_speed(self.needle_max_speed)

        self.syringe_home()
        self.needle_home()

    def disconnect(self):
        # put capper in its default state of "closed" before closing connection
        self.somatic.serial.close()
        self.logger.info("disconnected sampler")

    def syringe_set_max_speed(self, speed, wait=False):
        # speed is given in steps/s
        self.syringe_max_speed = speed
        self.logger.info(f"Set syringe max speed to {speed}.")
        self._execute(self.connection_info['syringe']['address'],
                      self.connection_info['syringe']['device_id'],
                      command=b'SPED', args=[speed], wait=wait)

    def needle_set_max_speed(self, speed, wait=False):
        self.needle_max_speed = speed
        self.logger.info(f"Set needle max speed to {speed}.")
        self._execute(self.connection_info['needle']['address'],
                      self.connection_info['needle']['device_id'],
                      command=b'SPED', args=[speed], wait=wait)

    def switch_valve(self, pos: int, wait=True):
        if pos != 0 and pos != 1:
            raise ValueError(f"Position {pos} is not possible.")
        self.logger.info(f"Switching valve to {pos}.")
        self._execute(address=self.connection_info['valve']['address'],
                      device_id=self.connection_info['valve']['device_id'],
                      command=b'SET', args=[pos], wait=wait)

    def set_syringe_flow_rate(self, flow_rate_ul_s, wait=False):
        self.syringe_set_max_speed(self._steps_per_volume * flow_rate_ul_s, wait=wait)

    def move_syringe(self, steps, wait=True, timeout_s=60*15):
        self._execute(address=self.connection_info['syringe']['address'],
                      device_id=self.connection_info['syringe']['device_id'],
                      command=b'MVRL', args=[steps], wait=wait, timeout_s=timeout_s)

    def refill_from_source(self, volume_ul: float, wait=True):
        self.switch_valve(pos=self.backing_solvent_port, wait=True)
        steps = int(round(-1 * self._steps_per_volume * volume_ul))
        if abs(steps + self.syringe_position) > abs(self.max_syringe_steps):
            raise ValueError(f"Volume {volume_ul} is not possible.")
        self.logger.info(f'Refilling syringe from source.')
        self.move_syringe(steps, wait)
        self.syringe_position += steps

    def dispense_ul(self, volume_ul: float, extra_wait_s=0, wait=True):
        steps = int(round(self._steps_per_volume * volume_ul))
        if abs(steps + self.syringe_position) > abs(self.max_syringe_steps):
            raise ValueError(f"Volume {volume_ul} is not possible.")
        self.logger.info(f"dispense {volume_ul} ul")
        self.switch_valve(pos=self.needle_port, wait=True)
        self.move_syringe(steps, wait)
        self.syringe_position += steps
        time.sleep(extra_wait_s)

    def aspirate_ul(self, volume_ul: float, extra_wait_s=0, wait=True):
        steps = int(round(-1 * self._steps_per_volume * volume_ul))
        if abs(steps + self.syringe_position) > abs(self.max_syringe_steps):
            raise ValueError(f"Volume {volume_ul} is not possible.")
        self.logger.info(f"Aspirating {volume_ul} ul with {steps} steps.")
        self.switch_valve(pos=self.needle_port, wait=True)
        self.move_syringe(steps, wait)
        self.syringe_position += steps
        time.sleep(extra_wait_s)

    def move_needle(self, position_mm, wait=True):
        """
        position_mm: negative to move needle down
        """
        steps = int(round(position_mm * self._steps_per_mm))
        if abs(steps + self.needle_position) > abs(self.max_needle_steps):
            raise ValueError(f"Position {position_mm} mm is not possible based on current position. Max steps is {self.max_needle_steps} and the target was {steps + self.syringe_position} steps")
        self.logger.info(f"Moving needle to {position_mm} mm ({steps} steps).")
        self._execute(address=self.connection_info['needle']['address'],
                      device_id=self.connection_info['needle']['device_id'],
                      command=b'MVRL', args=[steps], wait=wait)
        self.needle_position += steps
        
    def move_needle_to_absolute_position(self, absolute_position_mm, wait=True):
        """
        position_mm: negative to move needle down
        """
        steps = int(round((absolute_position_mm - self.needle_position/self._steps_per_mm) * self._steps_per_mm))
        if (abs(steps + self.needle_position) > abs(self.max_needle_steps)) or (absolute_position_mm > 0):
            raise ValueError(f"Position {absolute_position_mm} mm is not possible based on current position. Max steps is {self.max_needle_steps} and the target was {steps + self.needle_position} steps")
        self.logger.info(f"Moving needle to {absolute_position_mm} mm ({steps} steps).")
        self._execute(address=self.connection_info['needle']['address'],
                      device_id=self.connection_info['needle']['device_id'],
                      command=b'MVRL', args=[steps], wait=wait)
        self.needle_position += steps




    def syringe_set_acceleration(self, acceleration):
        self.syringe_acceleration = acceleration
        self.logger.info(f"Set syringe acceleration to {acceleration} steps/s/s.")
        self._execute(address=self.connection_info['syringe']['address'],
                      device_id=self.connection_info['syringe']['device_id'],
                      command=b'ACCL', args=[acceleration], wait=False)

        time.sleep(2)

    def needle_set_acceleration(self, acceleration):
        self.needle_acceleration = acceleration
        self.logger.info(f"Set needle acceleration to {acceleration} steps/s/s.")
        self._execute(address=self.connection_info['needle']['address'],
                      device_id=self.connection_info['needle']['device_id'],
                      command=b'ACCL', args=[acceleration], wait=False)

        time.sleep(2)

    def syringe_set_max_homing_speed(self, speed: int):
        self.logger.info(f"Set syringe home speed to {speed} steps/s.")
        self._execute(address=self.connection_info['syringe']['address'],
                      device_id=self.connection_info['syringe']['device_id'],
                      command=b'HMSD', args=[speed])

    def needle_set_max_homing_speed(self, speed: int):
        self.logger.info(f"Set needle home speed to {speed} steps/s.")
        self._execute(address=self.connection_info['needle']['address'],
                      device_id=self.connection_info['needle']['device_id'],
                      command=b'HMSD', args=[speed])

    def syringe_stop_motor(self):
        self.logger.info(f"Stopping syringe.")
        self._execute(address=self.connection_info['syringe']['address'],
                      device_id=self.connection_info['syringe']['device_id'],
                      command=b'STOP', args=[])

    def needle_stop_motor(self):
        self.logger.info(f"Stopping syringe.")
        self._execute(address=self.connection_info['needle']['address'],
                      device_id=self.connection_info['needle']['device_id'],
                      command=b'STOP', args=[])

    def syringe_home(self, direction=1, wait=True):
        self.logger.info(f"Homing syringe.")
        self._execute(address=self.connection_info['syringe']['address'],
                      device_id=self.connection_info['syringe']['device_id'],
                      command=b'HOME', args=[direction], wait=wait)
        self.syringe_position = 0

    def needle_home(self, direction=1, wait=True):
        self.logger.info(f"Homing needle.")
        self._execute(address=self.connection_info['needle']['address'],
                      device_id=self.connection_info['needle']['device_id'],
                      command=b'HOME', args=[direction], wait=wait)
        self.needle_position = 0

    def syringe_busy(self):
        syringe_response = self._execute(address=self.connection_info['syringe']['address'],
                                         device_id=self.connection_info['syringe']['device_id'],
                                         command=b'BUSY', args=[])
        return syringe_response

    def needle_busy(self):
        needle_response = self._execute(address=self.connection_info['needle']['address'],
                                        device_id=self.connection_info['needle']['device_id'],
                                        command=b'BUSY', args=[])

        return needle_response

    def get_syringe_speed(self):
        self.logger.info(f"Getting syringe speed.")
        response = self._get_data(address=self.connection_info['syringe']['address'],
                                  device_id=self.connection_info['syringe']['device_id'],
                                  command=b'GETS', args=[])

        self.logger.info(f"Syringe speed alarm value is {response}.")

        speed = 80000000 / (8 * 2) / response[0]    # MCU freq / (timer divider * interrupt divider) / alarm value
        self.logger.info(f"Syringe speed is {speed} steps/s.")

        return speed

    def get_needle_speed(self):
        self.logger.info(f"Getting needle speed.")
        response = self._get_data(address=self.connection_info['needle']['address'],
                                  device_id=self.connection_info['needle']['device_id'],
                                  command=b'GETS', args=[])

        self.logger.info(f"Needle speed alarm value is {response}.")

        speed = 80000000 / (8 * 2) / response[0]    # MCU freq / (timer divider * interrupt divider) / alarm value
        self.logger.info(f"Needle speed is {speed} steps/s.")

        return speed

    def get_valve_position(self):
        response = self.somatic.request(self.connection_info['valve']['address'], self.connection_info['valve']['device_id'], b'GET', [])

        return response

        # response = self._get_data(address=self.connection_info['valve']['address'],
        #                           device_id=self.connection_info['valve']['device_id'],
        #                           command=b'GET', args=[])
        #
        # return response[0]

    def get_is_running(self):
        self.logger.info(f"Checking busy status.")
        # Check if the syringe is busy
        syringe_response = self.syringe_busy()

        # Check if the needle is busy
        needle_response = self.needle_busy()

        # if syringe_response > 0 or needle_response > 0:
        if syringe_response > 0 or needle_response > 0:
            is_running = True
        else:
            is_running = False

        self.logger.info(f"Busy status is {is_running}.")

        return is_running

    def syringe_measure_current(self):
        self.logger.info(f"Measuring syringe motor current analogue.")
        syringe_response = self._execute(address=self.connection_info['syringe']['address'],
                                         device_id=self.connection_info['syringe']['device_id'],
                                         command=b'CRNT', args=[])
        self.logger.info(f"Measured a syringe motor current of {syringe_response}.")

        return syringe_response

    def needle_measure_current(self):
        self.logger.info(f"Measuring needle motor current analogue.")
        needle_response = self._execute(address=self.connection_info['needle']['address'],
                                        device_id=self.connection_info['needle']['device_id'],
                                        command=b'CRNT', args=[])
        self.logger.info(f"Measured a needle motor current of {needle_response}.")

        return needle_response

    def get_bubble_info(self):
        self.logger.info(f"Getting bubble information.")
        response = self._get_data(address=self.connection_info['bubble_sensor']['address'],
                                  device_id=self.connection_info['bubble_sensor']['device_id'],
                                  command=b'GETC', args=[])

        self.logger.info(f"Bubble count: {response[0]}, Max bubble period: {response[1]} ms")

        return response[0], response[1]

    def clear_bubble_info(self):
        self.logger.info(f"Clearing bubble information.")
        self._get_data(address=self.connection_info['bubble_sensor']['address'],
                       device_id=self.connection_info['bubble_sensor']['device_id'],
                       command=b'CLR', args=[])

    def get_bubble_sensor_state(self):
        self.logger.info(f"Getting bubble sensor state.")
        response = self._execute(address=self.connection_info['bubble_sensor']['address'],
                                 device_id=self.connection_info['bubble_sensor']['device_id'],
                                 command=b'GETS', args=[])

        self.logger.info(f"Liquid sensed: {response[0]}")

        return response[0]

    def reset(self):
        self.logger.info(f"Resetting MCU.")
        self._execute(address=self.connection_info['module']['address'],
                                        device_id=self.connection_info['module']['device_id'],
                                        command=b'RSET', args=[])

    def get_reset_flag(self):
        self.logger.info(f"Getting reset flag.")
        response = self._execute(address=self.connection_info['module']['address'],
                      device_id=self.connection_info['module']['device_id'],
                      command=b'GETR', args=[])
        self.logger.info(f"Reset flag is {response}.")

        return response

    def _execute(self, address: int, device_id: int, command: bytes, args: list[int], raise_error: bool = True,
                 include_status: bool = False, wait: bool = False, timeout_s: int = 120):
        try:
            response = self.somatic.request(address, device_id, command, args, raise_error, include_status)

            parsed_response = int.from_bytes(response, 'big')

            if not wait:
                return parsed_response

            # Wait for action to complete
            start_time = time.time()

            while self.get_is_running():
                # self.measure_syringe_current()
                if int(time.time() - start_time) > timeout_s:
                    raise Exception(f"Timeout Error: SALSA action took longer than {timeout_s}.")

        except SerialException:
            self.logger.warning(f'Retrying execute command')
            self.somatic.serial.close()
            self.somatic.serial.open()
            return self._execute(address, device_id, command, args, raise_error, include_status)

    def _get_data(self, address: int, device_id: int, command: bytes, args: list[int], raise_error: bool = True,
                 include_status: bool = False, wait: bool = False, timeout_s: int = 120):
        try:
            response = self.somatic.request_int(address, device_id, command, args, raise_error)

            return response

        except SerialException:
            self.logger.warning(f'Retrying execute command')
            self.somatic.serial.close()
            self.somatic.serial.open()
            return self._execute(address, device_id, command, args, raise_error, include_status)

    def profile_fitted_steps(self, volume_ul: float):
        """
        profile fitted steps per volume based on calibration curve
        :param volume_ul:
        :return:
        """
        return self.profile_slope * volume_ul + self.profile_intercept

    @property
    def steps_per_volume(self) -> float:
        return self._steps_per_volume

    @steps_per_volume.setter
    def steps_per_volume(self, value: float):
        self._steps_per_volume = value


def main(comport: str):
    x = EuropaControlV2(comport)
    # print(x.get_syringe_speed())
    # print(x.get_needle_speed())
    # x.syringe_set_max_speed(500)
    # print(x.get_syringe_speed())
    # x.needle_set_acceleration(2000)
    # x.needle_set_max_speed(1111)
    # print(x.get_needle_speed())
    # x.refill_from_source(600)
    # x.dispense_ul(600)
    # x.move_needle(3)
    # x.move_needle(50)
    # x.needle_home()
    print("here")
    # x.move_needle(-25)
    # print(x.needle_position)

    # x.dispense_ul(2000)
    # print(x.measure_syringe_current())
    # x.refill_from_source()

    # x.aspirate_ul(vol_in_ul)


def SalsaControl(*args, **kwargs) -> EuropaControlV2:
    warnings.warn(f'SalsaControl has been replaced with EuropaControl', DeprecationWarning, stacklevel=2)
    return EuropaControlV2(*args, **kwargs)


if __name__ == "__main__":
    main('COM11')
