from core.config_manager import get_config_manager
cfg = get_config_manager()
print('config_path=', cfg.config_path)
print('redis in raw_config=', 'redis' in cfg.raw_config)
print('raw_config keys=', list(cfg.raw_config.keys()))
print('\nraw_config["redis"]=' , cfg.raw_config.get('redis'))
