#!/usr/bin/env python3
"""
GPIO Demo - Control LEDs and Read Buttons
Built by Claude on Raspberry Pi 5

Example usage of GPIO pins on your Raspberry Pi.
Connect an LED to GPIO 17 (with resistor!) to see it blink.

Wiring:
  GPIO 17 --> 330 ohm resistor --> LED (+) --> LED (-) --> GND
  GPIO 27 --> Button --> GND (internal pull-up enabled)
"""

import time
import sys
from rich.console import Console
from rich.panel import Panel

console = Console()

# Check if running on actual Pi with GPIO
try:
    from gpiozero import LED, Button, Device
    from gpiozero.pins.lgpio import LGPIOFactory

    # Set the pin factory for Pi 5
    try:
        Device.pin_factory = LGPIOFactory()
        GPIO_AVAILABLE = True
    except Exception:
        GPIO_AVAILABLE = True  # Try anyway
except ImportError:
    GPIO_AVAILABLE = False


def blink_led(pin=17, times=10, interval=0.5):
    """Blink an LED connected to the specified GPIO pin"""
    if not GPIO_AVAILABLE:
        console.print("[red]GPIO not available[/red]")
        return

    console.print(Panel(
        f"[bold cyan]LED Blink Demo[/bold cyan]\n"
        f"[dim]Blinking LED on GPIO {pin} - {times} times[/dim]",
        border_style="cyan"
    ))

    try:
        led = LED(pin)
        console.print(f"\n[green]LED initialized on GPIO {pin}[/green]")

        for i in range(times):
            led.on()
            console.print(f"  [{i+1}/{times}] LED [yellow]ON[/yellow]")
            time.sleep(interval)

            led.off()
            console.print(f"  [{i+1}/{times}] LED [dim]OFF[/dim]")
            time.sleep(interval)

        led.close()
        console.print("\n[green]Demo complete![/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Make sure an LED is connected to the correct GPIO pin[/dim]")


def monitor_button(pin=27, timeout=30):
    """Monitor a button connected to the specified GPIO pin"""
    if not GPIO_AVAILABLE:
        console.print("[red]GPIO not available[/red]")
        return

    console.print(Panel(
        f"[bold cyan]Button Monitor Demo[/bold cyan]\n"
        f"[dim]Monitoring button on GPIO {pin} for {timeout} seconds[/dim]",
        border_style="cyan"
    ))

    try:
        button = Button(pin, pull_up=True)
        press_count = [0]

        def on_press():
            press_count[0] += 1
            console.print(f"  [green]Button PRESSED![/green] (Count: {press_count[0]})")

        def on_release():
            console.print(f"  [dim]Button released[/dim]")

        button.when_pressed = on_press
        button.when_released = on_release

        console.print(f"\n[yellow]Waiting for button presses... (Press Ctrl+C to stop)[/yellow]")

        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.1)

        button.close()
        console.print(f"\n[green]Demo complete! Total presses: {press_count[0]}[/green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def show_pinout():
    """Show GPIO pinout diagram"""
    pinout = """
    [bold cyan]Raspberry Pi 5 GPIO Pinout[/bold cyan]

           3V3  (1) (2)  5V
         GPIO2  (3) (4)  5V
         GPIO3  (5) (6)  GND
         GPIO4  (7) (8)  GPIO14
           GND  (9) (10) GPIO15
        GPIO17 (11) (12) GPIO18
        GPIO27 (13) (14) GND
        GPIO22 (15) (16) GPIO23
           3V3 (17) (18) GPIO24
        GPIO10 (19) (20) GND
         GPIO9 (21) (22) GPIO25
        GPIO11 (23) (24) GPIO8
           GND (25) (26) GPIO7
         GPIO0 (27) (28) GPIO1
         GPIO5 (29) (30) GND
         GPIO6 (31) (32) GPIO12
        GPIO13 (33) (34) GND
        GPIO19 (35) (36) GPIO16
        GPIO26 (37) (38) GPIO20
           GND (39) (40) GPIO21

    [dim]Pin 1 is on the left side near the USB-C power[/dim]
    """
    console.print(Panel(pinout, title="[green]GPIO Reference[/green]", border_style="green"))


def main():
    console.print(Panel(
        "[bold cyan]GPIO Demo Tools[/bold cyan]\n"
        "[dim]Built by Claude on Raspberry Pi 5[/dim]",
        border_style="cyan"
    ))

    if len(sys.argv) < 2:
        console.print("""
[yellow]Usage:[/yellow]
  python3 gpio_demo.py pinout     - Show GPIO pinout diagram
  python3 gpio_demo.py blink      - Blink LED on GPIO 17
  python3 gpio_demo.py blink 18   - Blink LED on GPIO 18
  python3 gpio_demo.py button     - Monitor button on GPIO 27
  python3 gpio_demo.py button 22  - Monitor button on GPIO 22

[dim]Note: Requires actual GPIO hardware connections[/dim]
""")
        return

    command = sys.argv[1].lower()

    if command == 'pinout':
        show_pinout()
    elif command == 'blink':
        pin = int(sys.argv[2]) if len(sys.argv) > 2 else 17
        blink_led(pin)
    elif command == 'button':
        pin = int(sys.argv[2]) if len(sys.argv) > 2 else 27
        monitor_button(pin)
    else:
        console.print(f"[red]Unknown command: {command}[/red]")


if __name__ == '__main__':
    main()
