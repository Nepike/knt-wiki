<?php
# Конфигурация вики IT-отдела.
#
# Основа — файл, сгенерированный установщиком MediaWiki 1.43.9.
# Секреты и адрес сервера НЕ хранятся здесь: они берутся из переменных окружения,
# которые docker-compose.yml передаёт из файла .env (см. .env.example).
#
# Все параметры: https://www.mediawiki.org/wiki/Manual:Configuration_settings

# Protect against web entry
if ( !defined( 'MEDIAWIKI' ) ) {
	exit;
}

/**
 * Значение переменной окружения; если её нет — ошибка, чтобы не запуститься
 * молча с пустым паролем или ключом.
 */
function itwikiEnv( string $name ): string {
	$value = getenv( $name );
	if ( $value === false || $value === '' ) {
		throw new RuntimeException( "Не задана переменная окружения $name (см. .env)" );
	}
	return $value;
}

## Название и адреса
$wgSitename = "Вики IT-отдела";

## Протокол и домен для абсолютных ссылок, например https://wiki.inbicst.ru
$wgServer = itwikiEnv( 'MW_SERVER' );
$wgScriptPath = "";
$wgResourceBasePath = $wgScriptPath;

## Короткие адреса вида /wiki/Страница (rewrite уже настроен в образе mediawiki)
$wgArticlePath = "/wiki/$1";
$wgUsePathInfo = true;

## На сервере запросы приходят от nginx через docker-сеть: доверяем его X-Forwarded-For,
## чтобы в истории правок и блокировках были реальные IP, а не адрес шлюза docker.
$wgCdnServersNoPurge = [ '172.16.0.0/12' ];

## Логотип КНТ | ИНБИКСТ (файлы в ./assets, исходник с прозрачным фоном — assets/logo-source.png).
## 'icon' — шапка Vector 2022 (шестиугольник со стрелками), '1x'/'2x' — для других тем.
$wgLogos = [
	'1x' => "$wgResourceBasePath/assets/logo-135.png",
	'2x' => "$wgResourceBasePath/assets/logo-270.png",
	'icon' => "$wgResourceBasePath/assets/logo-header.png",
];
$wgFavicon = "$wgResourceBasePath/assets/favicon.ico";

## Vector 2022 рисует иконку квадратом 50×50; наш логотип со стрелками шире (179×100 → 89×50).
$wgHooks['BeforePageDisplay'][] = static function ( OutputPage $out ) {
	$out->addInlineStyle( '.mw-logo .mw-logo-icon { width: 89px; height: 50px; }' );
};

## Язык и время
$wgLanguageCode = "ru";
$wgLocaltimezone = "Europe/Moscow";

## Почта. Пока SMTP не настроен, отключена полностью: аккаунты создают
## администраторы и сразу задают пароль.
$wgEnableEmail = false;
$wgEnableUserEmail = false; # UPO
$wgEmergencyContact = "";
$wgPasswordSender = "";
$wgEnotifUserTalk = false; # UPO
$wgEnotifWatchlist = false; # UPO
$wgEmailAuthentication = true;

## База данных
$wgDBtype = "mysql";
$wgDBserver = "db";
$wgDBname = itwikiEnv( 'MW_DB_NAME' );
$wgDBuser = itwikiEnv( 'MW_DB_USER' );
$wgDBpassword = itwikiEnv( 'MW_DB_PASSWORD' );
$wgDBprefix = "";
$wgDBssl = false;
$wgDBTableOptions = "ENGINE=InnoDB, DEFAULT CHARSET=binary";
$wgSharedTables[] = "actor";

## Кэш (APCu есть в образе)
$wgMainCacheType = CACHE_ACCEL;
$wgMemCachedServers = [];

## Загрузка файлов (скриншоты и документы для инструкций).
## Лимит размера на стороне PHP задаётся в php/uploads.ini.
$wgEnableUploads = true;
$wgFileExtensions = [ 'png', 'gif', 'jpg', 'jpeg', 'webp', 'pdf' ];
$wgUseImageMagick = true;
$wgImageMagickConvertCommand = "/usr/bin/convert";
$wgUseInstantCommons = false;

$wgPingback = false;

## Секреты — только из окружения
$wgSecretKey = itwikiEnv( 'MW_SECRET_KEY' );
# Changing this will log out all existing sessions.
$wgAuthenticationTokenVersion = "1";
$wgUpgradeKey = itwikiEnv( 'MW_UPGRADE_KEY' );

## Лицензия не указывается
$wgRightsPage = "";
$wgRightsUrl = "";
$wgRightsText = "";
$wgRightsIcon = "";

$wgDiff3 = "/usr/bin/diff3";

## Оформление
$wgDefaultSkin = "vector-2022";
wfLoadSkin( 'MinervaNeue' );
wfLoadSkin( 'MonoBook' );
wfLoadSkin( 'Timeless' );
wfLoadSkin( 'Vector' );

## Права доступа
# Читать могут все (вики публичная).
$wgGroupPermissions['*']['read'] = true;
# Анонимы не редактируют и не создают страницы.
$wgGroupPermissions['*']['edit'] = false;
$wgGroupPermissions['*']['createpage'] = false;
$wgGroupPermissions['*']['createtalk'] = false;
# Самостоятельная регистрация закрыта: аккаунты создают только администраторы
# через Служебная:Создать_учётную_запись (право createaccount у группы sysop есть по умолчанию).
$wgGroupPermissions['*']['createaccount'] = false;
$wgGroupPermissions['*']['autocreateaccount'] = false;
$wgGroupPermissions['sysop']['createaccount'] = true;

## Расширения
# Все входят в поставку MediaWiki 1.43. Подключаем только одобренные (см. CLAUDE.md).

# Визуальный редактор (Parsoid встроен в ядро, отдельный сервис не нужен)
wfLoadExtension( 'VisualEditor' );
# Одна вкладка «Править» с переключением визуальный/код внутри редактора
$wgVisualEditorUseSingleEditTab = true;

# Подсветка кода: <syntaxhighlight lang="bash">...</syntaxhighlight>
# (использует встроенный pygmentize, python3 есть в образе)
wfLoadExtension( 'SyntaxHighlight_GeSHi' );

# {{#if:}}, {{#time:}} и т.п. для шаблонов
wfLoadExtension( 'ParserFunctions' );

# Описание параметров шаблонов — VisualEditor показывает их как форму
wfLoadExtension( 'TemplateData' );
