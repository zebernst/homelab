// Torrent content layout: Original
// Default Torrent Management Mode: Automatic
// Default Save Path: /media/downloads/torrents/seeding
// Incomplete Save Path: /media/downloads/torrents/incomplete

module.exports = {
  apiKey: process.env.CROSS_SEED_API_KEY,
  action: "inject",
  delay: 30,
  duplicateCategories: false,
  excludeOlder: "4w",
  excludeRecentSearch: "2w",
  flatLinking: false,
  includeNonVideos: false,
  includeSingleEpisodes: true,
  linkCategory: "cross-seed",
  linkDir: "/media/downloads/qbittorrent/seeding/cross-seed",
  linkType: "hardlink",
  matchMode: "partial",
  outputDir: "/tmp",
  port: Number(process.env.CROSS_SEED_PORT),
  qbittorrentUrl: "http://qbittorrent.default.svc.cluster.local",
  radarr: [`http://radarr.default.svc.cluster.local/?apikey=${process.env.RADARR_API_KEY}`],
  searchCadence: "3d",
  skipRecheck: false,
  sonarr: [`http://sonarr.default.svc.cluster.local/?apikey=${process.env.SONARR_API_KEY}`],
  torrentDir: "/qbittorrent/qBittorrent/BT_backup",
  torznab: [
      2,  // PTP
      53, // HUNO
  ].map(i => `http://prowlarr.default.svc.cluster.local/${i}/api?apikey=${process.env.PROWLARR_API_KEY}`),
};
