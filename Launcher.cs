using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class NekoLauncher {
    // Импорт функций из WinAPI для загрузки библиотек
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Auto)]
    private static extern IntPtr LoadLibrary(string lpFileName);

    [DllImport("kernel32.dll", CharSet = CharSet.Ansi, ExactSpelling = true, SetLastError = true)]
    private static extern IntPtr GetProcAddress(IntPtr hModule, string procName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetDllDirectory(string lpPathName);

    // Описываем сигнатуру функции Py_Main из python312.dll
    // int Py_Main(int argc, wchar_t **argv)
    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private delegate int Py_Main(int argc, [MarshalAs(UnmanagedType.LPArray, ArraySubType = UnmanagedType.LPWStr)] string[] argv);

    [STAThread]
    public static void Main() {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        
        // Гарантируем корректный рабочий каталог вне зависимости от того, откуда запущен ярлык
        Directory.SetCurrentDirectory(baseDir);
        
        string pythonDir = Path.Combine(baseDir, "python");
        
        // ВАЖНО: Укажи здесь точное имя твоей DLL (python312.dll, python311.dll и т.д.)
        string dllName = "python312.dll"; 
        string pythonDllPath = Path.Combine(pythonDir, dllName);

        if (!File.Exists(pythonDllPath)) {
            MessageBox.Show("Критическая ошибка: Не найден файл " + dllName + " в папке 'python'.", "NekoFlow");
            return;
        }

        // 1. Добавляем папку python в пути поиска DLL, чтобы python312.dll нашел свои зависимости
        SetDllDirectory(pythonDir);

        // 2. Загружаем саму библиотеку Python
        IntPtr hPython = LoadLibrary(pythonDllPath);
        if (hPython == IntPtr.Zero) {
            MessageBox.Show("Не удалось загрузить ядро Python из " + dllName, "NekoFlow");
            return;
        }

        // 3. Ищем точку входа Py_Main
        IntPtr pPyMain = GetProcAddress(hPython, "Py_Main");
        if (pPyMain == IntPtr.Zero) {
            MessageBox.Show("Ошибка: В DLL не найдена функция Py_Main. Возможно, версия Python не поддерживается.", "NekoFlow");
            return;
        }

        Py_Main runPython = (Py_Main)Marshal.GetDelegateForFunctionPointer(pPyMain, typeof(Py_Main));

        // 4. Формируем аргументы так, как если бы мы запускали "pythonw.exe main.py"
        // Первый аргумент всегда имя программы, второй - скрипт
        string[] args = new string[] { "NekoFlow.exe", Path.Combine(baseDir, "main.py") };

        try {
            // ТЕПЕРЬ МЫ САМИ СТАЛИ ПИТОНОМ. 
            // Это блокирующий вызов. EXE не завершится, пока работает GUI.
            runPython(args.Length, args);
        } catch (Exception ex) {
            MessageBox.Show("Ошибка выполнения скрипта: " + ex.Message, "NekoFlow");
        }
    }
}