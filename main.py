import config
import logging
from telethon import TelegramClient

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    bot.run_until_disconnected()


if config.proxy:
    import socks
    proxy = (socks.SOCKS5, config.proxy_address, config.proxy_port)
    bot = TelegramClient('bot', config.api_id, config.api_hash, proxy=proxy).start(bot_token=config.token)
else:
    bot = TelegramClient('bot', config.api_id, config.api_hash).start(bot_token=config.token)


if __name__ == '__main__':
    main()