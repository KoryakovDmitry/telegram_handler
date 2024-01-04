pip3 uninstall telegram_handler -y
cd telegram_handler && python -m build && pip3 install --no-cache-dir dist/telegram_handler-1.4.6-py3-none-any.whl && cd ..