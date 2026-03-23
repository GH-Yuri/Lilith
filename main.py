import logging
import sys

from src.bot import Lilith
from src.config import AlpacaConfig, BotConfig


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    alpaca_config = AlpacaConfig.from_env()
    bot_config = BotConfig.from_env()

    bot = Lilith(alpaca_config, bot_config)
    bot.run()


if __name__ == "__main__":
    main()
