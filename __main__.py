#!/usr/bin/env python3

from bot import CryptoCallBot

def Main():
    bot = CryptoCallBot.GetInstance()
    bot.Run()

if __name__ == "__main__":
    Main()