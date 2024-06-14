CREATE TABLE `User` (
  `userID` varchar(100) NOT NULL,
  `email` TEXT NOT NULL, 
  `firstName` TEXT NOT NULL, 
  `lastName` TEXT NOT NULL, 
  `password` TEXT NOT NULL,
  `validated` BIT NOT NULL,
  `createdAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updatedAt` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`email`)
);

CREATE TABLE `Album` (
  `userID` varchar(100) NOT NULL,
  `albumID` varchar(100) NOT NULL,
  `name` TEXT NOT NULL,
  `description` TEXT NOT NULL,
  `thumbnailURL` TEXT NOT NULL,
  `createdAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`albumID`)
);

CREATE TABLE `Photo` (
  `userID` varchar(100) NOT NULL,
  `photoID` varchar(100) NOT NULL,
  `albumID` varchar(100) NOT NULL,
  `title` TEXT,
  `description` TEXT,
  `tags` TEXT,
  `photoURL` TEXT NOT NULL,
  `EXIF` TEXT,
  `createdAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updatedAt` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`photoID`),
  FOREIGN KEY (`albumID`) REFERENCES `Album` (`albumID`) ON DELETE CASCADE ON UPDATE CASCADE
);