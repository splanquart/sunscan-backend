import subprocess
import socket
import logging
import requests

def factory_power_helper():
    if is_battery_system_available():
        return PowerHelper()
    else:
        return MockPowerHelper()


def is_battery_system_available():
    try:
        # Vérifier si le port est ouvert
        with socket.create_connection(("127.0.0.1", 8423), timeout=1) as sock:
            # Tester la commande `get battery`
            ps = subprocess.Popen(('echo', 'get battery'), stdout=subprocess.PIPE)
            result = subprocess.check_output(('nc', '-q', '0', '127.0.0.1', '8423'), stdin=ps.stdout)
            ps.wait()
            result_str = result.decode('utf-8').rstrip()
            # Si une réponse valide est reçue, le système est disponible
            return "battery" in result_str.lower()
    except (socket.error, subprocess.CalledProcessError, ValueError):
        # Si une exception est levée, le système n'est pas disponible
        return False


class VoltageCheckMixin:
    """
    A mixin class for checking the stability of the battery voltage.
    Use only information from the Raspberry Pi's OS to check the voltage.

    You can use it with all PowerHelper classes.
    """
    def is_voltage_stable(self):
        """
        Check the stability of the battery voltage.

        This method runs a system command to get the battery voltage status.
        If the output indicates a low voltage, it returns False and prints a warning.
        Otherwise, it returns True and indicates that the voltage is stable.

        Returns:
            bool: True if the voltage is stable, False otherwise.
        """
        result = subprocess.run(['vcgencmd', 'get_throttled'], capture_output=True, text=True)
        # Typical output is in the form: "throttled=0x0" or "throttled=0x50000" for low voltage
        throttled = result.stdout.strip()
        if "0x50000" in throttled:
            print("⚠️ Low battery: Voltage too low detected!")
            return False
        else:
            print("✅ Voltage stable")
            return True

    def cpu_core_voltage(self):
        """
        Get the voltage of the CPU core.
        Typically, the core voltage is around 0.8V.

        Returns:
            float: The voltage of the CPU core, or None if an error occurs.
        """
        try:
            # Execute the command to get the core voltage
            result = subprocess.run(['vcgencmd', 'measure_volts', 'core'], 
                                    capture_output=True, text=True, check=True)
            # Typical output is in the form: "volt=0.8250V"
            voltage_str = result.stdout.strip()
            voltage_value = float(voltage_str.split('=')[1].replace('V', ''))
            return voltage_value
        except Exception as e:
            print(f"Error retrieving voltage: {e}")
            return None


class MockPowerHelper(VoltageCheckMixin):
    def get_battery(self):
        return 42.0
    def battery_power_plugged(self):
        return False
    def set_next_boot_datetime(self, datetime):
        return True
    def sync_time(self):
        pass


class PowerHelper(VoltageCheckMixin):
    """A helper class for managing power-related functions."""

    def __init__(self):
        """Initialize the PowerHelper class with a logger."""
        self.logger = logging.getLogger('maginkcal')

        try:
            # Set battery input protection 
            ps = subprocess.Popen(('echo', 'set_battery_input_protect true'), stdout=subprocess.PIPE)
            result = subprocess.check_output(('nc', '-q', '0', '127.0.0.1', '8423'), stdin=ps.stdout)
            ps.wait()
            
        except Exception as e:
            self.logger.info('Invalid battery')


    def get_battery(self):
        """
        Get the current battery level.

        Returns:
            float: The battery level as a float between 0 and 100,
                   or -1 if unable to retrieve the battery level.
        """
        # command = ['echo "get battery" | nc -q 0 127.0.0.1 8423']
        battery_float = -1
        try:
            ps = subprocess.Popen(('echo', 'get battery'), stdout=subprocess.PIPE)
            result = subprocess.check_output(('nc', '-q', '0', '127.0.0.1', '8423'), stdin=ps.stdout)
            ps.wait()
            result_str = result.decode('utf-8').rstrip()
            battery_level = result_str.split()[-1]
            battery_float = float(battery_level)
            


        except (ValueError, subprocess.CalledProcessError) as e:
            self.logger.info('Invalid battery output')
        return battery_float

    def battery_power_plugged(self):
        """
        Check if the battery is currently being charged.

        Returns:
            bool: True if the battery is plugged in and charging, False otherwise.
        """
        # command = ['echo "get battery_power_plugged" | nc -q 0 127.0.0.1 8423']
        battery_power_plugged = False
        try:
            ps = subprocess.Popen(('echo', 'get battery_power_plugged'), stdout=subprocess.PIPE)
            result = subprocess.check_output(('nc', '-q', '0', '127.0.0.1', '8423'), stdin=ps.stdout)
            ps.wait()
            result_str = result.decode('utf-8').rstrip()
            
            battery_res = result_str.split(': ')[-1]

            battery_power_plugged = True if battery_res == 'true' else False
        except (ValueError, subprocess.CalledProcessError) as e:
            self.logger.info('Invalid battery output')
        return battery_power_plugged

    def sync_time(self):
        """
        Synchronize the PiSugar RTC with the current system time.

        This method attempts to sync the RTC using a netcat command.
        If the sync fails, it logs an error message.
        """
        # To sync PiSugar RTC with current time
        try:
            ps = subprocess.Popen(('echo', 'rtc_rtc2pi'), stdout=subprocess.PIPE)
            result = subprocess.check_output(('nc', '-q', '0', '127.0.0.1', '8423'), stdin=ps.stdout)
            ps.wait()
        except subprocess.CalledProcessError:
            self.logger.info('Invalid time sync command')