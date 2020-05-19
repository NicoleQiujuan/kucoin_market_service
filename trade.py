#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
import time
import random
import logging
import consts as c
from kucoin.client import Trade, Market


def log_setting():
    logging.basicConfig(filename=c.LOG_FILE,
                        format='%(asctime)s - %(levelname)s - %(module)s - %(lineno)d:  %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S %p',
                        level=logging.WARNING)


class Kucoin(object):

    def __init__(self):
        # read configuration from json file
        with open(c.CONFIG_FILE, 'r') as file:
            config = json.load(file)

        self.api_key = config['kucoin_api_key']
        self.secret_key = config['kucoin_secret_key']
        self.pass_phrase = config['kucoin_pass_phrase']
        self.is_sandbox = config['is_sandbox']
        self.kucoin_symbol = config['kucoin_symbol']
        self.category = config['category']
        self.maker_number = config['maker_number']
        self.taker_number = config['taker_number']
        self.side = config['side']
        self.sizeMin = 100
        self.sizeMax = 10000

        self.buy_list = {}
        self.sell_list = {}
        self.best_ask = 0
        self.best_bid = 0
        self.market_price = 0

        self.trade_sandbox = Trade(self.api_key, self.secret_key, self.pass_phrase, is_sandbox=self.is_sandbox)
        self.market_sandbox = Market(self.api_key, self.secret_key, self.pass_phrase, is_sandbox=self.is_sandbox)
        self.trade = Trade(self.api_key, self.secret_key, self.pass_phrase, is_sandbox=False)
        self.market = Market(self.api_key, self.secret_key, self.pass_phrase, is_sandbox=False)

    def get_market_price(self):
        r = {}
        # 根据类型调用对应的合约API
        try:
            if self.category == c.BTC_USDT:
                r = self.market.get_ticker(self.kucoin_symbol)
            elif self.category == c.ETH_USDT:
                r = self.market.get_ticker(self.kucoin_symbol)
            elif self.category == c.ETH_BTC:
                r = self.market.get_ticker(self.kucoin_symbol)
        except Exception as e:
            logging.error(e)
            time.sleep(5)
        self.best_ask = int(float(r['bestAsk']))
        self.best_bid = int(float(r['bestBid']))
        self.market_price = int((self.best_ask + self.best_bid) / 2)
        logging.info('最新盘口价格 = %s' % self.market_price)

    def taker(self):
        try:
            t = self.market_sandbox.get_ticker(self.kucoin_symbol)
            logging.info(t)
            best_bid_size = t['bestBidSize']
            best_ask_size = t['bestAskSize']
            max_size = 100000
            if best_bid_size > max_size:
                best_bid_size = max_size
            if best_ask_size > max_size:
                best_ask_size = max_size

            if best_ask_size > 0:
                try:
                    sell = self.trade_sandbox.create_market_order(self.kucoin_symbol, 'sell', size=best_ask_size, type='market')
                    logging.info('在交易对 %s 以数量= %s, 吃卖单,订单ID = %s' %
                                 (self.kucoin_symbol, best_ask_size, sell['orderId']))
                except Exception as e:
                    logging.error(e)
            if best_bid_size > 0:
                try:
                    buy = self.trade_sandbox.create_market_order(self.kucoin_symbol, 'buy', size=best_bid_size, type='market')
                    logging.info('在交易对 %s 以数量= %s, 吃买单,订单ID = %s' %
                                 (self.kucoin_symbol, best_bid_size, buy['orderId']))
                except Exception as e:
                    logging.error(e)
        except Exception as e:
            logging.error(e)
            return

    def ask_maker(self, p):
        try:
            m = random.randint(self.sizeMin, self.sizeMax)
            ask = self.trade_sandbox.create_limit_order(self.kucoin_symbol, 'sell', m, p)
            logging.info('当前盘口价格 = %s,在交易对 %s 以数量= %s,价格= %s,创建了卖单,卖单ID = %s' %
                         (self.market_price, self.kucoin_symbol, m, p, ask['orderId']))
            self.sell_list[p] = {
                'price': p,
                'side': 'sell',
                'size': m,
                'order_id': ask['orderId']
            }
        except Exception as e:
            logging.error(e)

    def bid_maker(self, p):
        try:
            m = random.randint(self.sizeMin, self.sizeMax)
            bid = self.trade_sandbox.create_limit_order(self.kucoin_symbol, 'buy', m, p)
            logging.info('当前盘口价格 = %s,在交易对 %s 以数量= %s,价格= %s,创建了买单,卖单ID = %s' %
                         (self.market_price, self.kucoin_symbol, m, p, bid['orderId']))
            self.sell_list[p] = {
                'price': p,
                'side': 'buy',
                'size': m,
                'order_id': bid['orderId']
            }
        except Exception as e:
            logging.error(e)

    def cancel_order(self, order_id, key, side):
        try:
            self.trade_sandbox.cancel_order(order_id)
            logging.info('当前盘口价 = %s,撤单 id = %s, key = %s' % (self.market_price, order_id, key))
            if side == 'sell':
                del self.sell_list[key]
            elif side == 'buy':
                del self.buy_list[key]
        except Exception as e:
            logging.info('撤单时发生错误, order_id = %s, key = %s' % (order_id, key))
            logging.error(e)

    def get_order_info(self, order_id):
        try:
            o = self.trade_sandbox.get_order_details(order_id)
        except Exception as e:
            logging.error(e)
            o = {}
        return o

    def get_active_orders(self):
        try:
            o = self.trade_sandbox.get_order_list(symbol=self.kucoin_symbol, status='active', type='limit')
            os = o['items']
        except Exception as e:
            logging.error(e)
            os = []
        if len(os) > 0:
            self.sell_list.clear()
            self.buy_list.clear()
            for n in os:
                # print(json.dumps(n))
                if n['side'] == 'sell':
                    self.sell_list[int(n['price'])] = {
                        'price': int(n['price']),
                        'side': 'sell',
                        'size': n['size'],
                        'order_id': n['id']
                    }
                elif n['side'] == 'buy':
                    self.buy_list[int(n['price'])] = {
                        'price': int(n['price']),
                        'side': 'buy',
                        'size': n['size'],
                        'order_id': n['id']
                    }


if __name__ == '__main__':
    log_setting()
    logging.info('---------------------------------------')
    logging.info('Service Start ......')
    service = Kucoin()
    executor = ThreadPoolExecutor(max_workers=10)
    all_task = []
    while 1:
        service.get_market_price()
        service.taker()
        service.get_active_orders()
        ask_rand = service.market_price + service.maker_number - 1
        for k, v in list(service.sell_list.items()):
            # 判断范围，不在范围内的单撤掉
            if k not in range(service.market_price, ask_rand) and k in service.sell_list.keys():
                task = executor.submit(service.cancel_order, v['order_id'], k, 'sell')
                all_task.append(task)
        wait(all_task, return_when=ALL_COMPLETED)
        all_task.clear()

        bid_rand = service.market_price - service.maker_number + 1
        for k, v in list(service.buy_list.items()):
            # 判断范围，不在范围内的单撤掉
            if k not in range(bid_rand, service.market_price):
                task = executor.submit(service.cancel_order, v['order_id'], k, 'buy')
                all_task.append(task)
        wait(all_task, return_when=ALL_COMPLETED)
        all_task.clear()

        for i in range(1, service.maker_number):
            ask_price = service.market_price + i
            if ask_price in service.sell_list.keys():
                orderId = service.sell_list[ask_price]['order_id']
                order_info = service.get_order_info(orderId)
                if order_info:
                    if not order_info['isActive']:
                        task1 = executor.submit(service.cancel_order, orderId, ask_price, 'sell')
                        all_task.append(task1)
                        task2 = executor.submit(service.ask_maker, ask_price)
                        all_task.append(task2)
                    else:
                        size_dff = order_info['size'] - order_info['dealSize']
                        if size_dff not in range(service.sizeMin, service.sizeMax):
                            if order_info['isActive']:
                                task1 = executor.submit(service.cancel_order, order_info['id'], ask_price, 'sell')
                                all_task.append(task1)

                            task2 = executor.submit(service.ask_maker, ask_price)
                            all_task.append(task2)

            else:
                task2 = executor.submit(service.ask_maker, ask_price)
                all_task.append(task2)

            bid_price = service.market_price - i + 1
            if bid_price in service.buy_list.keys():
                orderId = service.buy_list[bid_price]['order_id']
                order_info = service.get_order_info(orderId)
                if order_info:
                    if not order_info['isActive']:
                        task1 = executor.submit(service.cancel_order, orderId, bid_price, 'buy')
                        all_task.append(task1)
                        task2 = executor.submit(service.bid_maker, bid_price)
                        all_task.append(task2)

                    else:
                        size_dff = order_info['size'] - order_info['dealSize']
                        if size_dff not in range(service.sizeMin, service.sizeMax):
                            if order_info['isActive']:
                                task1 = executor.submit(service.cancel_order, orderId, bid_price, 'buy')
                                all_task.append(task1)

                            task2 = executor.submit(service.bid_maker, bid_price)
                            all_task.append(task2)
            else:
                task2 = executor.submit(service.bid_maker, bid_price)
                all_task.append(task2)
        wait(all_task, return_when=ALL_COMPLETED)
        all_task.clear()

