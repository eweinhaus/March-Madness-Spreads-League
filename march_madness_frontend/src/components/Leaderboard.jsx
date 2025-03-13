import React from 'react';
import { Table, TableBody, TableCell, TableRow } from '@mui/material';

const Leaderboard = ({ leaderboard }) => {
  return (
    <Table>
      <TableBody>
        {leaderboard.map((entry, index) => (
          <TableRow key={entry.username}>
            <TableCell>{index + 1}</TableCell>
            <TableCell>{entry.full_name}</TableCell>
            <TableCell>{entry.total_points}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

export default Leaderboard; 