"""
test_distributed_spider_offline.py
-------------------------------------
Override DistributedEcommerceSpider supaya allowed_domains mengarah ke
local fixture server, dan redis_key terpisah dari nama produksi (supaya
tidak bentrok kalau ada proses lain pakai key yang sama).
"""

from scrapy_spider.spiders.ecommerce_distributed_spider import DistributedEcommerceSpider


class OfflineDistributedTestSpider(DistributedEcommerceSpider):
    name = "ecommerce_distributed_offline_test"
    allowed_domains = ["localhost", "127.0.0.1"]
    redis_key = "ecommerce_distributed_test:start_urls"
