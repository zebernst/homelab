// Torrent content layout: Original
// Default Torrent Management Mode: Automatic
// Default Save Path: /media/downloads/torrents/seeding
// Incomplete Save Path: /media/downloads/torrents/incomplete

module.exports = {
  apiKey: process.env.CROSS_SEED_API_KEY,
  port: Number(process.env.CROSS_SEED_PORT),

  action: "inject",
  delay: 30,
  flatLinking: false,
  includeSingleEpisodes: true,
  includeNonVideos: false,
  matchMode: "partial",

  dataDirs: [
    "/media/books",
    "/media/movies",
    "/media/tv",
    "/media/xxx"
  ],
  maxDataDepth: 3,
  searchCadence: "4w",
  excludeRecentSearch: "13w",
  excludeOlder: "1y",

  linkCategory: "cross-seed",
  linkDir: "/media/downloads/qbittorrent/seeding/cross-seed",
  linkType: "hardlink",

  radarr: [`http://radarr.default.svc.cluster.local/?apikey=${process.env.RADARR_API_KEY}`],
  sonarr: [`http://sonarr.default.svc.cluster.local/?apikey=${process.env.SONARR_API_KEY}`],
  torznab: [
      2,  // PTP
      12, // TL
      16, // GT
      18, // MLK
      19, // JPTV
      52, // SP
      53, // HUNO
      54, // HDS
  ].map(i => `http://prowlarr.default.svc.cluster.local/${i}/api?apikey=${process.env.PROWLARR_API_KEY}`),

  qbittorrentUrl: "http://qbittorrent.default.svc.cluster.local",
  duplicateCategories: false,
  skipRecheck: false,

  outputDir: "/tmp",
  torrentDir: null,
};
