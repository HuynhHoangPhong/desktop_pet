# Cute Desktop Pet

A Python/Tkinter-based desktop pet application that lives on your Windows desktop. 

## Features
- Always on top, transparent background
- Automatic walking and smooth animations
- Reacts to clicks (jumps and talks)
- Click and drag to reposition
- Right-click menu for settings and exit

## Structure
Make sure you have an `emotion` folder in the same directory as `main.py`. The required structure is:
```text
emotion/
    attack/
    hurt/
    idle/
    jump/
    run/
    runningjum/
    walk/
```
Inside each folder, animation frames must be properly sequenced (e.g., `tile000.png`, `tile001.png`, etc.).

## How to Run Locally
1. Ensure you have the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python main.py
   ```

## Troubleshooting
- **If the pet does not appear:** Check the `emotion` folder and ensure all files extracted properly. 
- **If attack doesn't work:** Check the folder name. It usually prefers `attack` but the system automatically corrects for `actack` if you've misspelled it!
- **If the animation looks jumpy:** Don't worry! This has been fixed in the latest version. Frames are automatically re-centered and normalized onto a stable `128x128` canvas so the pet doesn't bounce during mismatched frame changes!
- **How to build:** Run `build_exe.bat`

## How to Build Executable (.exe)
1. Double-click the `build_exe.bat` file.
2. The compiled executable will be automatically placed in the `dist/` folder named `CuteDesktopPet.exe`.
3. You can execute `CuteDesktopPet.exe` directly on Windows without needing Python installed.
