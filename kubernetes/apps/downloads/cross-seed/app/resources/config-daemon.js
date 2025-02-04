// Torrent content layout: Original
// Default Torrent Management Mode: Automatic
// Default Save Path: /media/downloads/torrents/seeding
// Incomplete Save Path: /media/downloads/torrents/incomplete

module.exports = {
  apiKey: process.env.CROSS_SEED_API_KEY,
  port: Number(process.env.CROSS_SEED_PORT),

  action: "inject",
  delay: 30,
  includeNonVideos: false,
  seasonFromEpisodes: 0.98,
  matchMode: "partial",

  linkCategory: "cross-seed",
  linkDirs: ["/media/downloads/qbittorrent/seeding/cross-seed"],
  linkType: "hardlink",

  radarr: [
    `http://radarr.downloads.svc.cluster.local/?apikey=$${process.env.RADARR_API_KEY}`,
    `http://radarr-uhd.downloads.svc.cluster.local/?apikey=$${process.env.RADARR_API_KEY}`,
  ],
  sonarr: [
    `http://sonarr.downloads.svc.cluster.local/?apikey=$${process.env.SONARR_API_KEY}`,
    `http://sonarr-uhd.downloads.svc.cluster.local/?apikey=$${process.env.SONARR_API_KEY}`,
  ],
  torznab: [], // only using autobrr announcements

  qbittorrentUrl: "http://qbittorrent.downloads.svc.cluster.local",
  duplicateCategories: false,
  skipRecheck: false,

  outputDir: "/config/torrents",
  useClientTorrents: true,
};
